"""Mechanical done gate (#8051, #8032 R1, #8048 R3/R6). Shipped command and functions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))

import dod  # noqa: E402
import pre_done_review  # noqa: E402


def _clean(**extra) -> dict:
    obs = {
        "proofs": [{"id": "pytest", "ran": True, "exit": 0}],
        "sources": ["honesty.py"],
        "tests": ["tests/scripts/test_honesty_8062.py"],
    }
    obs.update(extra)
    return obs


def test_open_pr_count_skipped_fails():
    reasons = pre_done_review.mechanical_problems(_clean(pr_create=True))
    assert "open-PR count skipped before create" in reasons


def test_required_proof_missing_fails():
    reasons = pre_done_review.mechanical_problems({"proof_required": True, "proofs": []})
    assert "required proof missing" in reasons


def test_sources_without_tests_fail():
    reasons = pre_done_review.mechanical_problems(
        {"proofs": [{"id": "pytest", "ran": True, "exit": 0}], "sources": ["a.py"], "tests": []}
    )
    assert "sources without tests" in reasons


def test_clean_fixture_passes():
    assert pre_done_review.mechanical_problems(_clean(pr_create=True, open_pr_count=1)) == []


def test_gate_cli_fails_when_rule_skipped(tmp_path: Path, capsys):
    path = tmp_path / "obs.json"
    path.write_text(json.dumps(_clean(pr_create=True)), encoding="utf-8")
    assert pre_done_review.main(["--gate", str(path)]) == 1
    assert "open-PR count skipped before create" in capsys.readouterr().out


def test_tool_py_pre_done_gate_fails_when_rule_skipped(tmp_path: Path):
    import subprocess

    path = tmp_path / "obs.json"
    path.write_text(json.dumps(_clean(pr_create=True)), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tool.py"), "pre-done", "--gate", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "open-PR count skipped before create" in completed.stdout


def test_unverified_write_needs_waiver():
    bare = pre_done_review.mechanical_problems(_clean(write_target="skill", verified_write=False))
    assert "anti-compounding: unverified write" in bare
    waived = pre_done_review.mechanical_problems(
        _clean(write_target="skill", verified_write=False, anti_compound_waiver="owner kept it a note")
    )
    assert "anti-compounding: unverified write" not in waived
    assert waived == []


def test_outbound_disclose_needs_check_or_waiver():
    bare = pre_done_review.mechanical_problems(
        _clean(outbound=True, agent_drafted=True, disclosed=False, claims=["ships Friday"], checked_claims=[])
    )
    assert "outbound disclose missing" in bare
    assert "outbound unchecked claims" in bare
    waived = pre_done_review.mechanical_problems(
        _clean(
            outbound=True,
            agent_drafted=True,
            disclosed=False,
            claims=["ships Friday"],
            outbound_waiver="not a send",
        )
    )
    assert waived == []


def test_agentic_pr_without_done_gate_fails_validator():
    rows = dod.evaluate(
        {
            "pr": {
                "labels": [{"name": "bug"}],
                "body": "<!-- chaos-engine:agentic -->\n\nFixes #1\n",
                "files": [],
            },
            "checks": [],
        }
    )
    assert dod.exit_code(rows) == 1
    assert any(name == "done-gate" and status == "gap" for name, status, _detail in rows)


def test_human_pr_is_exempt():
    rows = dod.evaluate(
        {"pr": {"labels": [{"name": "bug"}], "body": "Fixes #1\n", "files": []}, "checks": [], "human": True}
    )
    assert dod.exit_code(rows) == 0
    assert any(name == "done-gate" and status == "ok" for name, status, _detail in rows)
    marked = dod.evaluate(
        {
            "pr": {
                "labels": [{"name": "bug"}],
                "body": "<!-- chaos-engine:agentic -->\n\nFixes #1\n\ndone-gate: pass\n",
                "files": [],
            },
            "checks": [],
        }
    )
    assert any(name == "done-gate" and status == "ok" for name, status, _detail in marked)


def test_bot_entry_catalogue_names_a_command_per_mechanical_row():
    text = (ROOT / "references" / "bot-entry.md").read_text(encoding="utf-8")
    assert "## Mechanical gates" in text
    for command in (
        "tool.py pre-done --gate",
        "tool.py dod",
        "tool.py delete-check",
        "tool.py resume",
    ):
        assert command in text
    assert "Judgement stays prose" in text
