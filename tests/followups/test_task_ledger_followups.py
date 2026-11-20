"""Follow-ups #16 and #17: one planned-stop row, and a skipped swap stays skipped."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("task_ledger_followups", ROOT / "runtime" / "task_ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("CHAOS_ENGINE_TASKS_DIR", str(state / "tasks"))
    monkeypatch.setenv("CHAOS_ENGINE_SPEC_DIR", str(state / "specs"))
    monkeypatch.delenv("CHAOS_ENGINE_OWNER_FINISH_GOAL", raising=False)
    (state / "specs").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return _load()


def test_resume_of_duplicate_planned_stops_returns_one_row(ledger):
    ledger.record("t1", "commit", next_action="push", start=True, now=1_700_000_000)
    row = {"t": 1_700_000_100, ledger.PLANNED_STOP: "budget"}
    blob = json.dumps(row, separators=(",", ":")) + "\n"
    path = ledger.ledger("t1")
    path.write_text(path.read_text(encoding="utf-8") + blob + blob, encoding="utf-8")

    shown = [item for item in ledger.resume_rows("t1") if ledger.PLANNED_STOP in item]

    assert shown == [row]


def test_resume_does_not_reinsert_skipped_swap_step(ledger, monkeypatch):
    ledger.record(
        "t1", "plan", next_action="write code", prereqs=["swap"], start=True, now=1_700_000_000,
    )
    path = ledger.ledger("t1")
    skipped = {"t": 1_700_000_050, "step": "swap", "skipped": True, "next": "write code"}
    path.write_text(
        path.read_text(encoding="utf-8") + json.dumps(skipped, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        ledger, "check_prereq", lambda spec: (False, "swap: missing; re-add it before resuming"),
    )
    before = ledger.entries("t1")

    text = ledger.brief("t1")

    assert ledger.entries("t1") == before
    assert "re-add" not in text
    assert "prereq skipped: swap" in text
    assert text.startswith("Resume at: write code")
