"""Opt-in raise-the-bar (#8064). The shipped function does not emit a replacement."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))

import raise_the_bar  # noqa: E402


def test_typo_request_does_not_take_the_path():
    result = raise_the_bar.consider({"asked": "fix the typo on line 3 of the readme"})
    assert result == {"taken": False}


def test_replacement_stops_for_yes_and_does_not_emit_it():
    result = raise_the_bar.consider(
        {
            "asked": "raise the bar on this crash fix",
            "raise_bar": True,
            "replaces_deliverable": True,
            "replacement": "replace the surrounding workflow",
        }
    )
    assert result["taken"] is True
    assert result["stop_for_yes"] is True
    assert "replace the surrounding workflow" not in json.dumps(result)
    assert "replacement" not in result


def test_same_deliverable_harder_check_proceeds():
    result = raise_the_bar.consider(
        {
            "asked": "raise the bar on this crash fix",
            "raise_bar": True,
            "replaces_deliverable": False,
            "outcome": "the same crash fix held to a measured target",
            "used": ["outcome"],
            "skipped": ["other fields: they would add a second deliverable"],
            "check": "the crash fixture exits 0",
            "pass_line": "exit 0",
            "hard_target": 1,
            "measured": 1,
        }
    )
    assert result["stop_for_yes"] is False
    assert result["taken"] is True
    assert result["pass"] is True
    assert result["extra_deliverables"] is False


def test_missing_access_is_named_not_invented():
    result = raise_the_bar.consider(
        {
            "raise_bar": True,
            "asked": "raise the bar on the report",
            "missing_access": [{"name": "raw trace", "unlocks": "a measured baseline"}],
            "outcome": "the report matches the trace",
            "used": ["outcome"],
            "skipped": ["other fields"],
            "check": "numbers come from the trace",
            "pass_line": "every figure has a source",
        }
    )
    assert result["pass"] is False
    assert result["missing_access"][0]["name"] == "raw trace"
    assert result["missing_access"][0]["unlocks"] == "a measured baseline"
    assert result.get("baseline") is None
    blob = json.dumps(result)
    assert "99.9" not in blob
    for banned in ("rieseberg", "be-ambitious", "altitude", "craft anything", "cuga"):
        assert banned not in blob.casefold()


def test_missed_hard_target_with_evidence_is_not_a_pass():
    missed = raise_the_bar.consider(
        {
            "raise_bar": True,
            "asked": "aim higher on the suite",
            "hard_target": 90,
            "measured": 40,
            "outcome": "the suite holds a measured line",
            "check": "the outside count",
            "pass_line": "measured count reaches 90",
        }
    )
    assert missed["pass"] is False
    assert missed["honest_miss"] is True
    assert missed["measured"] == 40
    unrun = raise_the_bar.consider(
        {
            "raise_bar": True,
            "asked": "aim higher on the suite",
            "hard_target": 90,
            "outcome": "the suite holds a measured line",
            "check": "the outside count",
            "pass_line": "measured count reaches 90",
        }
    )
    assert unrun["pass"] is False
    assert unrun["unmeasured"] is True
    assert unrun.get("honest_miss") is not True
