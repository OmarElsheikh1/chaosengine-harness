"""Honesty fields (#8062 R1–R4). Calls shipped honesty functions, not copies."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import honesty  # noqa: E402


def test_unrun_check_marked_passed_is_rejected():
    check = {"id": "unit", "status": "passed", "ran": False, "howObtained": "guessed"}
    reasons = honesty.reject_unrun_pass([check])
    assert reasons == ["unrun check marked passed: unit"]
    receipt = {
        "schemaVersion": 1,
        "checks": [check],
        "howObtained": "guessed",
        "limitations": ["not-run"],
        "coverage": "unknown",
        "unknowns": [{"label": "unit", "settle": "re-run gate unit"}],
    }
    assert any(item == "unrun check marked passed: unit" for item in honesty.problems(receipt))


def test_unmeasured_is_not_a_pass():
    reasons = honesty.reject_unrun_pass(
        [{"id": "sim", "status": "passed", "ran": True, "howObtained": "guessed"}]
    )
    assert reasons == ["unmeasured is not a pass: sim"]
    assert honesty.score(
        {
            "checks": [{"id": "sim", "status": "passed", "ran": True, "howObtained": "guessed"}],
            "howObtained": "guessed",
            "limitations": ["guessed"],
            "coverage": "unknown",
            "unknowns": [{"label": "sim", "settle": "re-run gate sim"}],
        }
    )["pass"] is False


def test_measured_complete_receipt_stays_short():
    assert honesty.problems(
        {
            "checks": [{"id": "unit", "status": "passed", "ran": True, "howObtained": "measured"}],
            "coverage": "complete",
        }
    ) == []


def test_skipped_check_without_honesty_fields_fails_closed():
    reasons = honesty.problems({"checks": [{"id": "unit", "status": "skipped", "ran": False}]})
    assert any(item.startswith("honesty fields required:") for item in reasons)
    kept = honesty.score(
        {"checks": [{"id": "unit", "status": "skipped", "ran": False}], "limitations": ["kept"]}
    )
    assert kept["limitations"] == ["kept"]
    assert kept["pass"] is False


def test_unresolvable_check_does_not_retry():
    assert honesty.should_retry({"status": "failed", "canRefine": False}) is False
    assert honesty.should_retry({"status": "failed", "canRefine": True}) is True


def test_community_skill_always_on_needs_consent():
    assert honesty.community_always_on_problems(
        {"name": "extra", "tier": "community", "alwaysOn": True}
    ) == ["community skill always-on without consent"]
    assert honesty.community_always_on_problems(
        {"name": "extra", "tier": "community", "alwaysOn": True, "consent": "owner-2026-11-15"}
    ) == []
    assert honesty.community_always_on_problems({"name": "core", "tier": "core", "alwaysOn": True}) == []


def test_community_name_collision_is_refused():
    reasons = honesty.community_always_on_problems(
        {"name": "chaos-engine", "tier": "community", "alwaysOn": False},
        core_names={"chaos-engine"},
    )
    assert reasons == ["community skill name collides with core: chaos-engine"]


def test_newer_receipt_is_not_clobbered(tmp_path: Path):
    path = tmp_path / "receipt.json"
    honesty.save(path, {"schemaVersion": 2, "coverage": "complete", "checks": []})
    with pytest.raises(honesty.NewerReceiptError):
        honesty.save(path, {"schemaVersion": 1, "coverage": "complete", "checks": []})
    assert json.loads(path.read_text(encoding="utf-8"))["schemaVersion"] == 2


def test_older_receipt_loads_after_migration(tmp_path: Path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"schemaVersion": 0, "task": "t-old"}) + "\n", encoding="utf-8")
    loaded = honesty.load(path)
    assert loaded["schemaVersion"] == honesty.SCHEMA_VERSION
    assert loaded["task"] == "t-old"
    assert loaded["coverage"] == "unknown"
    assert json.loads(path.read_text(encoding="utf-8"))["schemaVersion"] == 0


def test_secret_in_settlement_hint_is_stripped(tmp_path: Path):
    path = tmp_path / "receipt.json"
    honesty.save(
        path,
        {
            "schemaVersion": 1,
            "coverage": "unknown",
            "howObtained": "guessed",
            "limitations": ["secret-hint"],
            "checks": [],
            "unknowns": [{"label": "unit", "settle": "token=sk-plantedsecret99"}],
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "sk-plantedsecret99" not in text
    assert "[redacted]" in text


def test_save_rejects_unrun_pass(tmp_path: Path):
    path = tmp_path / "lie.json"
    with pytest.raises(honesty.HonestyError):
        honesty.save(
            path,
            {
                "schemaVersion": 1,
                "checks": [{"id": "unit", "status": "passed", "ran": False}],
                "howObtained": "guessed",
                "limitations": ["not-run"],
                "coverage": "unknown",
                "unknowns": [{"label": "unit", "settle": "re-run gate unit"}],
            },
        )
    assert not path.exists()
