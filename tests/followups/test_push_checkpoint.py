"""#15: PostToolUse on git push or gh pr writes a task checkpoint."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "guard.py"


def _ledger():
    spec = importlib.util.spec_from_file_location("task_ledger_push", ROOT / "task_ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(tmp_path: Path, command: str) -> subprocess.CompletedProcess[str]:
    ledger = _ledger()
    state = tmp_path / "state"
    work = tmp_path / "work"
    work.mkdir()
    os.environ["CHAOS_ENGINE_TASKS_DIR"] = str(state / "tasks")
    os.environ["CHAOS_ENGINE_SPEC_DIR"] = str(state / "specs")
    (state / "specs").mkdir(parents=True)
    ledger.record("t1", "plan", workdir=str(work), next_action="open the pull request", start=True)
    event = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "cwd": str(work),
        "session_id": "followups-push-checkpoint",
        "tool_input": {"command": command},
        "tool_response": {"exit_code": 0, "stdout": ""},
    }
    env = {
        **os.environ,
        "CHAOS_ENGINE_TASKS_DIR": str(state / "tasks"),
        "CHAOS_ENGINE_SPEC_DIR": str(state / "specs"),
        "CHAOS_ENGINE_STORE_REFRESH": "0",
        "CHAOS_ENGINE_PROTECTED_CHECKOUTS": str(ROOT),
    }
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(work),
    )
    return result, ledger


def test_post_tool_use_git_push_writes_checkpoint(tmp_path):
    result, ledger = _run(tmp_path, "git push -u origin ChaosEngine/harness-followups")
    assert result.returncode == 0, result.stderr
    steps = [row.get("step") for row in ledger.entries("t1")]
    assert "push" in steps


def test_post_tool_use_gh_pr_writes_checkpoint(tmp_path):
    result, ledger = _run(tmp_path, "gh pr create --title followups --body body")
    assert result.returncode == 0, result.stderr
    steps = [row.get("step") for row in ledger.entries("t1")]
    assert "pr" in steps
