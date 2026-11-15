"""#8052 R1-R2: offline layout conformance and docs drift. No network. No model API."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hosts = load(ROOT / "hosts.py", "ce_hosts_8052")
        cls.conformance = load(ROOT / "conformance.py", "ce_conformance_8052")

    def _write_current(self, project: Path) -> None:
        (project / "AGENTS.md").write_text(self.hosts.instruction_block(), encoding="utf-8")
        (project / "CLAUDE.md").write_bytes(self.hosts.claude_pointer_bytes())
        (project / "GEMINI.md").write_bytes(
            self.hosts.import_pointer_instruction(None, relative="GEMINI.md")
        )
        github = project / ".github"
        github.mkdir()
        (github / "copilot-instructions.md").write_text(
            self.hosts.copilot_instruction_block(), encoding="utf-8",
        )
        codex = project / ".codex"
        codex.mkdir()
        (codex / "config.toml").write_bytes(self.hosts.codex_content(None, with_mcp=False))
        (codex / "hooks.json").write_bytes(self.hosts.lifecycle_hooks_document("codex"))
        grok = project / ".grok" / "hooks"
        grok.mkdir(parents=True)
        (grok / "lifecycle.json").write_bytes(self.hosts.lifecycle_hooks_document("grok"))
        gemini = project / ".gemini"
        gemini.mkdir()
        raw = self.hosts.json_content(None, relative=".gemini/settings.json", with_mcp=False)
        merged = self.hosts.hook_content(
            self.hosts.without_chaos_hooks(raw, "Gemini"),
            self.hosts.gemini_hooks_document(),
            "Gemini",
        )
        (gemini / "settings.json").write_bytes(merged)

    def test_current_install_passes_and_pins_match_excerpts(self):
        fixture = self.conformance.load_fixture()
        self.assertIn("future", fixture)
        self.assertNotIn("golden", fixture["name"])
        for pin in fixture["pins"]:
            self.assertEqual(pin["content_sha256"], self.conformance.excerpt_hash(pin["recorded_excerpt"]))
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self._write_current(project)
            self.assertEqual([], self.conformance.check_layout(project, fixture))

    def test_wrong_filename_and_disallowed_keys_fail(self):
        fixture = self.conformance.load_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self._write_current(project)
            (project / "CLAUDE.md").unlink()
            (project / "CLAUDE.txt").write_text(self.hosts.instruction_block(), encoding="utf-8")
            errors = self.conformance.check_layout(project, fixture)
            self.assertTrue(any("CLAUDE.md" in item for item in errors))
            self.assertTrue(any("CLAUDE.txt" in item for item in errors))

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self._write_current(project)
            gemini = project / ".gemini" / "settings.json"
            document = json.loads(gemini.read_text(encoding="utf-8"))
            document["not_in_pin"] = True
            document["context"] = {"fileName": "AGENTS.md", "apiKey": "nope"}
            gemini.write_text(json.dumps(document), encoding="utf-8")
            codex = project / ".codex" / "config.toml"
            codex.write_text(codex.read_text(encoding="utf-8") + "not_in_pin = true\n", encoding="utf-8")
            grok = project / ".grok" / "hooks" / "lifecycle.json"
            hook = json.loads(grok.read_text(encoding="utf-8"))
            hook["not_in_pin"] = True
            grok.write_text(json.dumps(hook), encoding="utf-8")
            rules = project / ".cursor" / "rules"
            rules.mkdir(parents=True)
            (rules / "policy.md").write_text("ignored plain markdown\n", encoding="utf-8")
            errors = self.conformance.check_layout(project, fixture)
            self.assertTrue(any("not_in_pin" in item and "settings.json" in item for item in errors))
            self.assertTrue(any("context.apiKey" in item for item in errors))
            self.assertTrue(any("not_in_pin" in item and "config.toml" in item for item in errors))
            self.assertTrue(any("not_in_pin" in item and "lifecycle.json" in item for item in errors))
            self.assertTrue(any("plain markdown rule" in item for item in errors))

    def test_planted_hash_mismatch_is_reported_with_the_pin(self):
        pin = {
            "id": "claude",
            "url": "https://code.claude.com/docs/en/claude-md",
            "content_sha256": self.conformance.excerpt_hash("original"),
        }

        def fetch(_url: str) -> tuple[int, bytes]:
            return 200, b"changed"

        result = self.conformance.check_docs_drift([pin], fetch)[0]
        self.assertEqual("fail", result["status"])
        self.assertIn(pin["url"], result["pin"])
        self.assertIn(pin["url"], result["detail"])
        self.assertIn("update the fixture", result["detail"])

    def test_withheld_network_and_http_5xx_are_not_a_pass(self):
        pin = {
            "url": "https://geminicli.com/docs/cli/gemini-md/",
            "content_sha256": "abc",
        }

        def withheld(_url: str) -> tuple[int, bytes]:
            raise ConnectionError("network withheld")

        def unavailable(_url: str) -> tuple[int, bytes]:
            return 503, b""

        down = self.conformance.check_docs_drift([pin], withheld)[0]
        server = self.conformance.check_docs_drift([pin], unavailable)[0]
        self.assertEqual("error", down["status"])
        self.assertNotEqual("pass", down["status"])
        self.assertIn(pin["url"], down["detail"])
        self.assertEqual("skip-with-warning", server["status"])
        self.assertNotEqual("pass", server["status"])
        self.assertIn("503", server["detail"])
        self.assertIn(pin["url"], server["detail"])

    def test_five_tool_layouts_match_pinned_fixtures(self):
        fixture = self.conformance.load_fixture()
        self.assertEqual(
            ["claude", "codex", "gemini", "cursor", "grok"],
            list(fixture["tools"]),
        )
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self._write_current(project)
            layouts = self.conformance.check_tool_layouts(project, fixture)
            for tool, errors in layouts.items():
                self.assertEqual([], errors, tool)

    def test_failed_fetch_is_not_unchanged(self):
        pin = {
            "url": "https://cursor.com/docs/rules",
            "content_sha256": "abc",
        }

        def withheld(_url: str) -> tuple[int, bytes]:
            raise ConnectionError("network withheld")

        def unavailable(_url: str) -> tuple[int, bytes]:
            return 503, b""

        for result in (
            self.conformance.check_docs_drift([pin], withheld)[0],
            self.conformance.check_docs_drift([pin], unavailable)[0],
        ):
            self.assertEqual("fetch-failed", result["classification"])
            self.assertNotEqual("unchanged", result["classification"])
            self.assertNotIn("unchanged", result["detail"])

    def test_disagreeing_published_example_fails_or_warns(self):
        fixture = self.conformance.load_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            pages = Path(temporary)
            for tool, entry in (
                ("claude", "CLAUDE.txt"),
                ("codex", "AGENTS.md"),
                ("gemini", "GEMINI.md"),
                ("cursor", "AGENTS.md"),
                ("grok", "AGENTS.md"),
            ):
                (pages / f"{tool}.md").write_text(
                    f"<!-- host-doc-example: {tool}\nentry: {entry}\npaths: {entry}\n-->\n",
                    encoding="utf-8",
                )
            findings = self.conformance.published_example_findings(pages, fixture)
        self.assertTrue(any(item.startswith("fail:") and "disagrees" in item for item in findings))
        self.assertEqual([], self.conformance.published_example_findings(ROOT / "guides" / "tools", fixture))

    def test_unmeasured_golden_check_is_not_a_pass(self):
        corpus = self.conformance.load_golden_corpus()
        task = corpus["tasks"][0]
        scored = self.conformance.run_golden_task(task)
        self.assertNotEqual("pass", scored["overall"])
        self.assertIn(scored["overall"], {"unknown", "skipped"})
        planted = self.conformance.ledger_check_status({"id": "guessed", "status": "pass", "measured": False})
        self.assertNotEqual("pass", planted)
        self.assertEqual("unknown", planted)


if __name__ == "__main__":
    unittest.main()
