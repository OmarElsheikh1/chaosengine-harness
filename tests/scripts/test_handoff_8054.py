"""One handoff object (#8054, #8032 R2, #8048 R5). Resume reads the receipt."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))

import handoff_receipt  # noqa: E402
import task_ledger  # noqa: E402


def test_resume_from_receipt_alone(tmp_path: Path):
    receipt = handoff_receipt.build(
        task="gate",
        head_sha="abc123def456",
        branch="ChaosEngine/epic-8056-h-behavior",
        pr="12",
        changed_paths=["honesty.py", "handoff_receipt.py", "tests/scripts/test_handoff_8054.py"],
        verified=[{"command": "pytest", "exit": 0, "when": "2026-11-15T00:00:00Z", "howObtained": "measured"}],
        open_next="ship the gate",
        blockers=[],
        outcome="shipped the honesty gate for the harness",
        usage_ref="sess-1",
        coverage="complete",
        unknowns=[],
    )
    path = handoff_receipt.write(tmp_path, "gate", receipt)
    text = handoff_receipt.resume_from_receipt(handoff_receipt.read(tmp_path, "gate"))
    assert "abc123def456" in text
    assert "ship the gate" in text
    assert "verification: passed" in text
    outcome_lines = [line for line in text.splitlines() if line.startswith("outcome:")]
    assert outcome_lines == ["outcome: shipped the honesty gate for the harness"]
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["usageRef"] == "sess-1"
    assert "totals" not in stored
    assert "promptTokens" not in path.read_text(encoding="utf-8")


def test_partial_coverage_and_unknowns_stay_unknown(tmp_path: Path):
    receipt = handoff_receipt.build(
        task="gate",
        head_sha="abc123def456",
        open_next="rerun the open check",
        verified=[{"command": "pytest", "exit": 0, "howObtained": "measured"}],
        coverage="partial",
        unknowns=[{"label": "e2e", "settle": "re-run gate e2e"}],
        outcome="unknown",
    )
    handoff_receipt.write(tmp_path, "gate", receipt)
    text = handoff_receipt.resume_from_receipt(handoff_receipt.read(tmp_path, "gate"))
    assert "verification: unknown" in text
    assert handoff_receipt.read(tmp_path, "gate")["unknowns"][0]["label"] == "e2e"


def test_planted_secret_in_command_argument_is_not_stored(tmp_path: Path):
    receipt = handoff_receipt.build(
        task="gate",
        head_sha="abc123def456",
        open_next="next",
        verified=[
            {
                "command": "pytest --token sk-plantedsecret99",
                "exit": 0,
                "arguments": ["--token", "sk-plantedsecret99"],
                "howObtained": "measured",
            }
        ],
        coverage="partial",
        unknowns=[{"label": "tok", "settle": "api_key=sk-plantedsecret99"}],
        outcome="unknown",
    )
    path = handoff_receipt.write(tmp_path, "gate", receipt)
    text = path.read_text(encoding="utf-8")
    assert "sk-plantedsecret99" not in text
    assert "arguments" not in text


def test_resume_cli_prints_receipt_without_ledger(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("CHAOS_ENGINE_TASKS_DIR", str(tmp_path))
    handoff_receipt.write(
        tmp_path,
        "t1",
        handoff_receipt.from_step(task="t1", head="cafebabe1234", next_step="ship the gate"),
    )
    assert task_ledger.main(["t1"], "resume") == 0
    out = capsys.readouterr().out
    assert "cafebabe1234" in out
    assert "ship the gate" in out
    assert "verification: unknown" in out
    assert out.count("outcome:") == 1


def test_checkpoint_resume_prints_recorded_sha(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("CHAOS_ENGINE_TASKS_DIR", str(tmp_path / "tasks"))
    monkeypatch.setenv("CHAOS_ENGINE_SPEC_DIR", str(tmp_path / "specs"))
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "spec-t1.md").write_text("spec\n", encoding="utf-8")
    monkeypatch.setattr(task_ledger, "REFUSED_VOLATILE_ROOTS", ("/nonexistent-volatile-root",))
    monkeypatch.setattr(task_ledger, "VOLATILE_FS_TYPES", frozenset())
    work = tmp_path / "work"
    work.mkdir()
    assert task_ledger.main(
        ["t1", "plan", "--start", "--workdir", str(work), "--head", "deadbeef1234", "--next", "run the suite"]
    ) == 0
    capsys.readouterr()
    assert task_ledger.main(["t1"], "resume") == 0
    out = capsys.readouterr().out
    assert out.startswith("Resume at: run the suite")
    assert "deadbeef1234" in out
    assert "verification: unknown" in out
    stored = json.loads((tmp_path / "tasks" / "t1.handoff.json").read_text(encoding="utf-8"))
    assert stored["usageRef"] == ""
    assert "localPromptTokens" not in stored
