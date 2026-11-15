"""Build the portable chaos-engine agent plugin from this repository."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ci.assemble_chaos_engine_plugin import assemble  # noqa: E402
from scripts.ci.check_plugin_changelog_version import defects, engine_version  # noqa: E402


def _runtime_names() -> list[str]:
    manifest = json.loads((ROOT / "distributions.json").read_text(encoding="utf-8"))
    files = manifest["distributions"]["portable"]["runtimeFiles"]
    return ["__main__.py", "tool.py", *files]


class AssembleChaosEnginePluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.package = Path(self.temporary.name) / "chaos-engine"

    def test_cli_builds_this_repo_package(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, engine_version(ROOT))
        self.assertEqual([], defects(ROOT))
        home = Path(self.temporary.name) / "home"
        home.mkdir()
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["GROK_HOME"] = str(home / ".grok")
        script = ROOT / "scripts/ci/assemble_chaos_engine_plugin.py"
        completed = subprocess.run(
            [sys.executable, str(script), str(self.package), "--repository-root", str(ROOT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

        for relative in ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            manifest = json.loads((self.package / relative).read_text(encoding="utf-8"))
            self.assertEqual(version, manifest["version"])
            self.assertEqual("chaos-engine", manifest["name"])
        self.assertEqual(
            (ROOT / "agent-plugins/chaos-engine/CHANGELOG.md").read_bytes(),
            (self.package / "CHANGELOG.md").read_bytes(),
        )
        self.assertEqual(
            (ROOT / "agent-plugins/chaos-engine/COMPATIBILITY.md").read_bytes(),
            (self.package / "COMPATIBILITY.md").read_bytes(),
        )
        self.assertIn(f"## {version}", (self.package / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.assertIn(version, (self.package / "COMPATIBILITY.md").read_text(encoding="utf-8"))
        self.assertEqual(
            (ROOT / "references/ui-delivery.md").read_bytes(),
            (self.package / "references/ui-delivery.md").read_bytes(),
        )
        self.assertEqual(
            (ROOT / "skills/chaos-engine/SKILL.md").read_bytes(),
            (self.package / "skills/chaos-engine/SKILL.md").read_bytes(),
        )
        self.assertTrue((self.package / "references/delegate-card.md").is_file())
        self.assertFalse((self.package / "packs/shaft").exists())
        self.assertFalse((self.package / "profiles/shaft").exists())
        self.assertFalse((self.package / "bin/chaosengine-harness.js").exists())
        mcp = json.loads((self.package / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(["./bin/chaos-engine.pyz", "mcp"], mcp["mcpServers"]["chaosengine"]["args"])
        runtime = self.package / "bin/chaos-engine.pyz"
        with zipfile.ZipFile(runtime) as archive:
            self.assertEqual(sorted(_runtime_names()), sorted(archive.namelist()))
        help_run = subprocess.run(
            [sys.executable, str(runtime), "--help"],
            cwd=self.temporary.name,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(0, help_run.returncode, help_run.stderr)
        self.assertIn("usage: tool.py", help_run.stdout)

    def test_two_builds_match_byte_for_byte(self) -> None:
        second = Path(self.temporary.name) / "second"
        assemble(ROOT, self.package)
        assemble(ROOT, second)
        first_files = sorted(
            path.relative_to(self.package).as_posix()
            for path in self.package.rglob("*")
            if path.is_file()
        )
        second_files = sorted(
            path.relative_to(second).as_posix() for path in second.rglob("*") if path.is_file()
        )
        self.assertEqual(first_files, second_files)
        for relative in first_files:
            self.assertEqual(
                (self.package / relative).read_bytes(),
                (second / relative).read_bytes(),
                relative,
            )

    def test_missing_runtime_source_names_the_file(self) -> None:
        source = Path(self.temporary.name) / "source"
        _fixture_repository(source, kernel=False)
        with self.assertRaises(ValueError) as caught:
            assemble(source, self.package)
        self.assertIn("hooks/kernel.py", str(caught.exception))
        self.assertFalse(self.package.exists())

    def test_version_flag_must_match_version_file(self) -> None:
        with self.assertRaises(ValueError) as caught:
            assemble(ROOT, self.package, version="0.0.0")
        self.assertIn(engine_version(ROOT), str(caught.exception))
        self.assertFalse(self.package.exists())

    def test_output_inside_the_repository_is_rejected(self) -> None:
        source = Path(self.temporary.name) / "source"
        source.mkdir()
        (source / "VERSION").write_text("1.2.3\n", encoding="utf-8")
        output = source / "inside"
        with self.assertRaises(ValueError) as caught:
            assemble(source, output)
        self.assertIn("overlap", str(caught.exception))
        self.assertFalse(output.exists())


def _fixture_repository(source: Path, *, kernel: bool) -> None:
    source.mkdir()
    (source / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    (source / "LICENSE").write_text("test license\n", encoding="utf-8")
    (source / "distributions.json").write_text(
        json.dumps({"distributions": {"portable": {"runtimeFiles": ["hooks/kernel.py"]}}}) + "\n",
        encoding="utf-8",
    )
    (source / "tool.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    plugin = source / "agent-plugins/chaos-engine"
    plugin.mkdir(parents=True)
    (plugin / "CHANGELOG.md").write_text("# Changelog\n\n## 1.2.3 - 2026-11-15\n", encoding="utf-8")
    (plugin / "COMPATIBILITY.md").write_text("chaos-engine 1.2.3\n", encoding="utf-8")
    skill = source / "skills/chaos-engine/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# skill\n", encoding="utf-8")
    if kernel:
        hook = source / "hooks/kernel.py"
        hook.parent.mkdir(parents=True)
        hook.write_text("# kernel\n", encoding="utf-8")
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, "init", "--quiet"], cwd=source, check=True)
    subprocess.run([git, "add", "--", "."], cwd=source, check=True)


if __name__ == "__main__":
    unittest.main()
