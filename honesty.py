#!/usr/bin/env python3
"""Honesty vocabulary for receipts (ShaftHQ/SHAFT_ENGINE#8062 R1–R4).

Stdlib only. No skill. ``save`` refuses an unrun or unmeasured pass and
refuses to overwrite a newer ``schemaVersion``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA_VERSION = 1
PASS_STATUS = frozenset({"passed", "pass", "green"})
MEASURED = frozenset({"measured", "computed"})
SECRET_TOKEN = re.compile(r"(?:sk-|ghp_|github_pat_)[A-Za-z0-9_\-]{8,}")
SECRET_ASSIGN = re.compile(r"(?i)\b(api[_-]?key|secret|token|password|bearer)\s*[=:]\s*\S+")
DROP_KEYS = frozenset({
    "arguments", "args", "prompt", "prompts", "result", "results",
    "stderr", "stdout", "error", "toolarguments",
})


class HonestyError(ValueError):
    """A receipt claims a pass the checks do not support."""


class NewerReceiptError(ValueError):
    """An older writer must not overwrite a newer schema."""


def scrub_text(text: str) -> str:
    text = SECRET_TOKEN.sub("[redacted]", text)
    return SECRET_ASSIGN.sub(lambda match: f"{match.group(1)}=[redacted]", text)


def scrub(value: object) -> object:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).casefold().replace("_", "") in DROP_KEYS:
                continue
            cleaned[key] = scrub(item)
        return cleaned
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        return scrub_text(value)
    return value


def reject_unrun_pass(checks: object) -> list[str]:
    """Unrun or unmeasured checks must not be marked passed."""
    reasons: list[str] = []
    if not isinstance(checks, list):
        return reasons
    for check in checks:
        if not isinstance(check, dict):
            continue
        status = str(check.get("status", "")).strip().casefold()
        if status not in PASS_STATUS:
            continue
        name = str(check.get("id") or "?")
        if check.get("ran") is not True:
            reasons.append(f"unrun check marked passed: {name}")
        elif check.get("howObtained") not in MEASURED:
            reasons.append(f"unmeasured is not a pass: {name}")
    return reasons


def _needs_honesty_fields(receipt: dict) -> bool:
    checks = receipt.get("checks") or []
    if not isinstance(checks, list):
        return True
    coverage = receipt.get("coverage")
    if coverage in {"partial", "unknown"}:
        return True
    if not checks and coverage in {None, "complete"}:
        return False
    for check in checks:
        if not isinstance(check, dict):
            return True
        status = str(check.get("status", "")).strip().casefold()
        if (
            check.get("ran") is not True
            or check.get("howObtained") not in MEASURED
            or status in {"skipped", "unrun", "unknown", "partial"}
        ):
            return True
    return False


def problems(receipt: object) -> list[str]:
    """Fail closed. An empty list means the receipt may be stored."""
    if not isinstance(receipt, dict):
        return ["honesty fields required: receipt"]
    reasons = reject_unrun_pass(receipt.get("checks") or [])
    coverage = receipt.get("coverage")
    verdict = str(receipt.get("status") or receipt.get("verdict") or "").casefold()
    if coverage in {"partial", "unknown"} and verdict in PASS_STATUS:
        reasons.append(f"unmeasured is not a pass: coverage {coverage}")
    if _needs_honesty_fields(receipt):
        for field in ("howObtained", "limitations", "coverage", "unknowns"):
            if field not in receipt:
                reasons.append(f"honesty fields required: {field}")
    for unknown in receipt.get("unknowns") or []:
        if isinstance(unknown, dict):
            settle = unknown.get("settle")
            if isinstance(settle, str) and settle != scrub_text(settle):
                reasons.append("secret in settlement hint")
    return reasons


def should_retry(check: object) -> bool:
    """False when another turn cannot resolve the failure."""
    if not isinstance(check, dict) or check.get("canRefine") is False:
        return False
    return str(check.get("status", "")).casefold() in {"failed", "fail"}


def score(receipt: object) -> dict:
    """Keep limitations attached. Problems are not a pass."""
    body = receipt if isinstance(receipt, dict) else {}
    limitations = body.get("limitations")
    found = problems(body)
    return {
        "pass": not found,
        "limitations": list(limitations) if isinstance(limitations, list) else [],
        "problems": found,
    }


def community_always_on_problems(
    record: object,
    *,
    core_names: set[str] | None = None,
) -> list[str]:
    """A community skill is not always-on without a recorded owner action."""
    if not isinstance(record, dict):
        return ["community skill always-on without consent"]
    reasons: list[str] = []
    tier = str(record.get("tier") or "").casefold()
    name = str(record.get("name") or "")
    untrusted = tier in {"community", "untrusted"}
    if untrusted and record.get("alwaysOn") and not str(record.get("consent") or "").strip():
        reasons.append("community skill always-on without consent")
    if untrusted and core_names and name in core_names:
        reasons.append(f"community skill name collides with core: {name}")
    return reasons


def _schema_of(payload: dict) -> int:
    value = payload.get("schemaVersion", SCHEMA_VERSION)
    if isinstance(value, bool) or not isinstance(value, int):
        return SCHEMA_VERSION
    return value


def save(path: Path, payload: dict) -> None:
    """Write JSON. Refuse a dishonest pass and a newer on-disk schema."""
    if not isinstance(payload, dict):
        raise HonestyError("receipt must be an object")
    cleaned = scrub(payload)
    if not isinstance(cleaned, dict):
        raise HonestyError("receipt must be an object")
    denied = [
        item for item in problems(cleaned)
        if item.startswith("unrun check marked passed") or item.startswith("unmeasured is not a pass")
    ]
    if denied:
        raise HonestyError(denied[0])
    writer = _schema_of(cleaned)
    cleaned["schemaVersion"] = writer
    target = Path(path)
    if target.is_file():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            existing = {}
        current = existing.get("schemaVersion") if isinstance(existing, dict) else None
        if isinstance(current, int) and not isinstance(current, bool) and current > writer:
            raise NewerReceiptError(f"newer receipt schema {current} left untouched")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(cleaned, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)


def load(path: Path) -> dict:
    """Read a receipt. Older schemas migrate in memory and are not rewritten."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise HonestyError("receipt must be an object")
    version = raw.get("schemaVersion") or 0
    if isinstance(version, bool) or not isinstance(version, int):
        version = 0
    if version > SCHEMA_VERSION:
        loaded = dict(raw)
        loaded["_readOnly"] = True
        return loaded
    loaded = dict(raw)
    loaded["schemaVersion"] = SCHEMA_VERSION
    loaded.setdefault("coverage", "unknown")
    loaded.setdefault("outcome", "unknown")
    return loaded
