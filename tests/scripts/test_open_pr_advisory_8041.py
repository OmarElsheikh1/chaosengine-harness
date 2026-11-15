"""#8041-#8044: open-PR advisory recognizes -R, pages past 30, and loud-fails bad UTF-8."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class OpenPrAdvisoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard = load(ROOT / "hooks" / "guard.py", "ce_guard_open_pr_8041")

    def test_repo_flag_before_pr_advises_at_the_cap_and_is_silent_under_it(self):
        self.assertEqual("create", self.guard._open_pr_verb(["-R", "ShaftHQ/SHAFT_ENGINE", "pr", "create"]))
        self.assertEqual("ready", self.guard._open_pr_verb(["--repo", "o/r", "pr", "ready", "-R", "other/repo"]))
        self.assertIsNone(self.guard._open_pr_verb(["pr", "list"]))
        self.assertIsNone(self.guard._open_pr_verb(["issue", "create"]))
        self.assertTrue(self.guard._open_pr_action(("gh -R ShaftHQ/SHAFT_ENGINE pr create",)))
        self.assertFalse(self.guard._open_pr_action(("gh pr list",)))
        event = {"hook_event_name": "PreToolUse", "cwd": str(ROOT)}
        with mock.patch.object(self.guard, "_open_pr_numbers", return_value=[1, 2]):
            _block, note = self.guard._open_pr_pretool(event, "PreToolUse", ("gh -R o/r pr create",))
        self.assertIn("at the cap (2 of 2)", note or "")
        with mock.patch.object(self.guard, "_open_pr_numbers", return_value=[1]):
            _block, note = self.guard._open_pr_pretool(event, "PreToolUse", ("gh -R o/r pr reopen",))
        self.assertIsNone(note)

    def test_thirty_one_open_pull_requests_are_not_counted_as_thirty(self):
        rows = [{"number": index, "state": "OPEN"} for index in range(1, 32)]

        def fake_run(argv, **_kwargs):
            limit = int(argv[argv.index("--limit") + 1])
            page = rows if limit >= 31 else rows[:30]
            return subprocess.CompletedProcess(argv, 0, json.dumps(page), "")

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(self.guard.shutil, "which", return_value="gh"), mock.patch.object(
            self.guard.subprocess, "run", side_effect=fake_run
        ) as ran:
            numbers = self.guard._open_pr_numbers(Path(temporary))
        self.assertEqual(31, len(numbers or []))
        self.assertNotEqual(30, len(numbers or []))
        limit_used = int(ran.call_args.args[0][ran.call_args.args[0].index("--limit") + 1])
        self.assertGreater(limit_used, 30)

    def test_non_utf8_config_exits_without_a_decision_block(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "chaos-engine" / "hooks" / "open-pr-advisory.json"
            config.parent.mkdir(parents=True)
            config.write_bytes(b"\xff")
            cap, problem = self.guard._open_pr_cap(root)
            self.assertEqual(0, cap)
            self.assertIn("open-pr-advisory.json", problem)
            self.assertIn("UTF-8", problem)
            event = {
                "hook_event_name": "PreToolUse",
                "cwd": str(root),
                "session_id": "open-pr-utf8",
                "tool_name": "Bash",
                "tool_input": {"command": "gh pr create"},
            }
            stdout = __import__("io").StringIO()
            stderr = __import__("io").StringIO()
            with mock.patch.object(sys, "stdout", stdout), mock.patch.object(sys, "stderr", stderr):
                code = self.guard._run_event(event, "portable")
        self.assertEqual(2, code)
        self.assertNotIn('"decision": "block"', stdout.getvalue())
        self.assertNotIn('"decision":"block"', stdout.getvalue())
        self.assertIn("open-pr-advisory.json", stderr.getvalue())

    def test_default_cap_is_one_stream_until_config_sets_streams(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cap, problem = self.guard._open_pr_cap(root)
            self.assertEqual("", problem)
            self.assertEqual(2, cap)
            config = root / "chaos-engine" / "hooks" / "open-pr-advisory.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"reviewWip": 2, "streams": 2}), encoding="utf-8")
            raised, raised_problem = self.guard._open_pr_cap(root)
        self.assertEqual("", raised_problem)
        self.assertEqual(4, raised)
        kanban = (ROOT / "skills" / "kanban" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("default stays one stream", kanban)


if __name__ == "__main__":
    unittest.main()
