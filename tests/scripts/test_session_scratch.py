"""Session scratch folder and the one-hour session-end retrospective."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks/guard.py"


def load_scratch():
    spec = importlib.util.spec_from_file_location(
        "session_scratch_under_test", ROOT / "hooks/session_scratch.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def isolated_env(temporary: str) -> dict[str, str]:
    protected = [
        item
        for item in os.environ.get("CHAOS_ENGINE_PROTECTED_CHECKOUTS", "").split(os.pathsep)
        if item
    ]
    protected.append(str(ROOT))
    return {
        **os.environ,
        "TMPDIR": temporary,
        "TEMP": temporary,
        "TMP": temporary,
        "CHAOS_ENGINE_PROTECTED_CHECKOUTS": os.pathsep.join(protected),
        "CHAOS_ENGINE_STORE_REFRESH": "0",
    }


class SessionScratchTest(unittest.TestCase):
    def test_root_and_subagent_share_one_folder(self):
        scratch = load_scratch()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertTrue(scratch.ensure(project, "same-session"))
            self.assertFalse(scratch.ensure(project, "same-session"))
            scratch.append_note(
                project, "same-session", agent="root", kind="thinking", text="choose the small fix"
            )
            scratch.open_agent(project, "same-session", "reviewer")
            scratch.append_note(
                project,
                "same-session",
                agent="reviewer",
                kind="enhancement",
                text="file the hook gap",
            )
            notes = scratch.load_notes(project, "same-session")
            self.assertEqual(
                ["thinking", "enhancement"],
                [note["kind"] for note in notes],
            )
            self.assertEqual(["reviewer"], scratch.open_agents(project, "same-session"))
            rule = (project / ".grok/rules/session-scratch.md").read_text(encoding="utf-8")
            self.assertIn(scratch.relative_folder("same-session"), rule)
            self.assertNotIn(str(project), rule)

    def test_notes_drop_secrets_and_home_paths(self):
        scratch = load_scratch()
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            scratch.append_note(
                project,
                "redact",
                agent="root",
                kind="thinking",
                text="token=abc123 see /home/someone/secret",
            )
            text = scratch.load_notes(project, "redact")[0]["text"]
            self.assertNotIn("abc123", text)
            self.assertNotIn("/home/someone", text)
            self.assertIn("[redacted]", text)
            self.assertIn("[path]", text)

    def test_retrospective_runs_once_after_one_hour_and_files_one_issue(self):
        scratch = load_scratch()
        calls: list[list[str]] = []

        def run(args: list[str]) -> tuple[int, str]:
            calls.append(args)
            if "list" in args:
                return 0, "[]"
            return 0, "https://github.com/ShaftHQ/chaosengine-harness/issues/74\n"

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            scratch.append_note(
                project, "long", agent="root", kind="enhancement", text="wait until session end"
            )
            scratch.append_note(
                project, "long", agent="root", kind="enhancement", text="wait until session end"
            )
            early = scratch.retrospective(project, "long", 60, run=run)
            self.assertIsNone(early)
            self.assertEqual([], calls)
            report = scratch.retrospective(project, "long", 3601, run=run)
            self.assertIn("wait until session end", report)
            self.assertIn("https://github.com/ShaftHQ/chaosengine-harness/issues/74", report)
            self.assertIsNone(scratch.retrospective(project, "long", 99999, run=run))
        creates = [args for args in calls if "create" in args]
        self.assertEqual(1, len(creates))

    def test_timed_out_create_stays_pending_and_a_later_retrospective_files_it_once(self):
        scratch = load_scratch()
        text = "retry the unfiled enhancement"
        url = "https://github.com/ShaftHQ/chaosengine-harness/issues/82"
        creates: list[list[str]] = []
        create_result = {"code": 124, "stdout": ""}

        def run(args: list[str]) -> tuple[int, str]:
            if len(args) >= 3 and args[1] == "issue" and args[2] == "create":
                creates.append(args)
                return create_result["code"], create_result["stdout"]
            if len(args) >= 3 and args[1] == "issue" and args[2] == "list":
                return 0, "[]"
            return 0, ""

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            scratch.append_note(project, "retry", agent="root", kind="enhancement", text=text)
            first = scratch.retrospective(project, "retry", 3601, run=run)
            self.assertIsNotNone(first)
            self.assertIn(text, first)
            self.assertIn("Not filed in this pass:", first)
            self.assertNotIn(url, first)
            stored = scratch.load_notes(project, "retry")
            self.assertIn(text, [note["text"] for note in stored])
            done = scratch.folder(project, "retry") / "retro.done"
            create_result["code"] = 0
            create_result["stdout"] = url + "\n"
            second = scratch.retrospective(project, "retry", 7202, run=run)
            self.assertIsNotNone(
                second,
                "retro.done must not drop an unfiled note; done existed=%s" % done.exists(),
            )
            self.assertIn(url, second)
            self.assertNotIn("Not filed in this pass:", second)
            third = scratch.retrospective(project, "retry", 10803, run=run)
            self.assertIsNone(third)
            self.assertEqual(2, len(creates))
            self.assertTrue(done.is_file())

    def test_default_gh_runner_stops_inside_file_budget(self):
        scratch = load_scratch()
        self.assertLessEqual(scratch.FILE_BUDGET_SECONDS, 2.0)
        text = "do not let the host kill cut the write"
        url = "https://github.com/ShaftHQ/chaosengine-harness/issues/83"
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            bin_dir = project / "bin"
            bin_dir.mkdir()
            gh = bin_dir / "gh"
            gh.write_text("#!/bin/sh\nsleep 30\nexit 0\n", encoding="utf-8")
            gh.chmod(0o755)
            scratch.append_note(project, "budget", agent="root", kind="enhancement", text=text)
            previous = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{previous}"
            try:
                started = time.monotonic()
                report = scratch.retrospective(project, "budget", scratch.ONE_HOUR_SECONDS + 1)
                elapsed = time.monotonic() - started
            finally:
                os.environ["PATH"] = previous
            self.assertIsNotNone(report)
            self.assertIn(text, report)
            self.assertLess(elapsed, 3.0)
            self.assertLess(elapsed, scratch.FILE_BUDGET_SECONDS + 0.9)

            def run(args: list[str]) -> tuple[int, str]:
                if len(args) >= 3 and args[1] == "issue" and args[2] == "list":
                    return 0, "[]"
                if len(args) >= 3 and args[1] == "issue" and args[2] == "create":
                    return 0, url + "\n"
                return 0, ""

            follow = scratch.retrospective(
                project, "budget", scratch.ONE_HOUR_SECONDS + 2, run=run
            )
            self.assertIsNotNone(follow)
            self.assertIn(url, follow)

    def test_distinct_notes_that_share_a_title_prefix_are_both_filed(self):
        scratch = load_scratch()
        prefix = "p" * 72
        calls: list[list[str]] = []

        def run(args: list[str]) -> tuple[int, str]:
            calls.append(args)
            if "list" in args:
                return 0, "[]"
            return 0, "https://github.com/ShaftHQ/chaosengine-harness/issues/80\n"

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            scratch.append_note(
                project, "long", agent="root", kind="enhancement", text=prefix + " alpha"
            )
            scratch.append_note(
                project, "long", agent="root", kind="enhancement", text=prefix + " beta"
            )
            report = scratch.retrospective(project, "long", 3601, run=run)
        creates = [args for args in calls if "create" in args]
        self.assertEqual(2, len(creates))
        titles = [args[args.index("--title") + 1] for args in creates]
        self.assertNotEqual(titles[0], titles[1])
        self.assertIn("alpha", report or "")
        self.assertIn("beta", report or "")

    def test_stop_does_not_demand_a_retrospective_and_session_end_runs_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            env = isolated_env(temporary)
            started = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import importlib.util, sys; "
                    "spec = importlib.util.spec_from_file_location('ce_reflection', sys.argv[1]); "
                    "module = importlib.util.module_from_spec(spec); "
                    "spec.loader.exec_module(module); "
                    "module.record_session_start('retro-end', '2020-01-01T00:00:00+00:00')",
                    str(ROOT / "hooks/reflection.py"),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(0, started.returncode, started.stderr)
            scratch = load_scratch()
            scratch.append_note(
                project, "retro-end", agent="root", kind="enhancement", text="share one report"
            )
            bin_dir = project / "bin"
            bin_dir.mkdir()
            log = project / "gh.log"
            gh = bin_dir / "gh"
            gh.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$@\" >> \"$GH_LOG\"\n"
                "if [ \"$1\" = issue ] && [ \"$2\" = list ]; then echo '[]'; exit 0; fi\n"
                "if [ \"$1\" = issue ] && [ \"$2\" = create ]; then "
                "echo 'https://github.com/ShaftHQ/chaosengine-harness/issues/74'; exit 0; fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            gh.chmod(0o755)
            env = {**env, "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}", "GH_LOG": str(log)}
            stop = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "Stop",
                        "session_id": "retro-end",
                        "cwd": str(project),
                        "last_assistant_message": "still working",
                    }
                ),
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertNotIn("Terminal reflection required", stop.stdout)
            self.assertNotEqual("block", json.loads(stop.stdout or "{}").get("decision"))
            first = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(
                    {"hook_event_name": "SessionEnd", "session_id": "retro-end", "cwd": str(project)}
                ),
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            second = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(
                    {"hook_event_name": "SessionEnd", "session_id": "retro-end", "cwd": str(project)}
                ),
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertIn("share one report", first.stdout)
            self.assertIn("https://github.com/ShaftHQ/chaosengine-harness/issues/74", first.stdout)
            self.assertNotIn("Session retrospective", second.stdout)
            self.assertEqual(1, log.read_text(encoding="utf-8").count("create"))
            short = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(
                    {
                        "hook_event_name": "SessionEnd",
                        "session_id": "retro-short",
                        "cwd": str(project / "short"),
                    }
                ),
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertNotIn("Session retrospective", short.stdout)


if __name__ == "__main__":
    unittest.main()
