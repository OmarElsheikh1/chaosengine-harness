"""Offline host-doc layout and docs-drift checks.

Reads a fixture tree and pinned hashes. Does not start a vendor CLI and does
not call a model API. A withheld network or HTTP 5xx is an error or a
skip-with-warning, never a pass. Live multi-model runs stay future.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Callable

FIXTURE = Path(__file__).resolve().parents[1] / "evals" / "host-doc-conformance.json"
GOLDEN_CORPUS = Path(__file__).resolve().parents[1] / "evals" / "golden-tasks" / "corpus.json"
TOOL_IDS = ("claude", "codex", "gemini", "cursor", "grok")
EXAMPLE_BLOCK = re.compile(r"<!--\s*host-doc-example:\s*(\S+)\s*(.*?)-->", re.DOTALL)
Fetch = Callable[[str], tuple[int, bytes]]


def load_fixture(path: Path | None = None) -> dict:
    """Load the committed host-doc fixture."""
    return json.loads((path or FIXTURE).read_text(encoding="utf-8"))


def excerpt_hash(excerpt: str) -> str:
    """SHA-256 of a recorded pin excerpt. Not a live page fetch."""
    return hashlib.sha256(excerpt.encode("utf-8")).hexdigest()


def check_layout(tree: Path, fixture: dict | None = None) -> list[str]:
    """Fail a wrong filename, a missing required path, or a disallowed config key."""
    spec = fixture if fixture is not None else load_fixture()
    root = Path(tree)
    errors: list[str] = []
    for relative in spec.get("required_paths", []):
        if not (root / relative).is_file():
            errors.append(f"missing required path {relative}")
    for relative in spec.get("forbidden_filenames", []):
        if (root / relative).exists():
            errors.append(f"policy at disallowed filename {relative}")
    for relative, limit in spec.get("max_lines", {}).items():
        path = root / relative
        if path.is_file() and len(path.read_text(encoding="utf-8").splitlines()) > int(limit):
            errors.append(f"{relative} exceeds {limit} lines")
    for relative, limit in spec.get("max_bytes", {}).items():
        path = root / relative
        if path.is_file() and path.stat().st_size > int(limit):
            errors.append(f"{relative} exceeds {limit} bytes")
    for relative, allowed in spec.get("config_files", {}).items():
        path = root / relative
        if not path.is_file():
            continue
        try:
            keys = _config_keys(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, ValueError) as exc:
            errors.append(f"{relative}: unreadable config ({exc})")
            continue
        allowed_keys = set(allowed.get("keys", []))
        for key in sorted(keys - allowed_keys):
            errors.append(f"disallowed config key {key} in {relative}")
        nested = _context_keys(path)
        if nested is not None:
            allowed_context = set(allowed.get("context_keys", []))
            for key in sorted(nested - allowed_context):
                errors.append(f"disallowed config key context.{key} in {relative}")
    rules_dir = spec.get("cursor_rules_dir")
    if rules_dir:
        rules = root / rules_dir
        if rules.is_dir():
            for path in sorted(rules.iterdir()):
                if path.is_file() and path.suffix == ".md":
                    errors.append(f"cursor: plain markdown rule is ignored: {path.name}")
    return errors


def _config_keys(path: Path) -> set[str]:
    data = _load_config(path)
    if not isinstance(data, dict):
        raise ValueError("config is not an object")
    return {str(key) for key in data}


def _context_keys(path: Path) -> set[str] | None:
    data = _load_config(path)
    if not isinstance(data, dict):
        return None
    context = data.get("context")
    if not isinstance(context, dict):
        return None
    return {str(key) for key in context}


def _load_config(path: Path) -> object:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    if path.suffix == ".toml":
        return tomllib.loads(text)
    raise ValueError(f"unsupported config type {path.suffix}")


def check_docs_drift(pins: list[dict], fetch: Fetch) -> list[dict]:
    """Compare each pin to fetch(url). Fetch failure is never a pass.

    status is pass, fail, error, or skip-with-warning.
    HTTP 5xx is skip-with-warning. A connection failure is error.
    A hash mismatch fails and names the pin.
    """
    results: list[dict] = []
    if not pins:
        return [{"pin": "", "status": "error", "detail": "no pins to check"}]
    for pin in pins:
        results.append(_one_pin(pin, fetch))
    return results


def _drift_classification(status: str) -> str:
    """Map a pin result to unchanged, changed, or fetch-failed.

    A withheld network or an HTTP error is fetch-failed. It is never unchanged.
    """
    if status == "pass":
        return "unchanged"
    if status == "fail":
        return "changed"
    return "fetch-failed"


def _drift_row(label: str, status: str, detail: str) -> dict:
    return {
        "pin": label,
        "status": status,
        "classification": _drift_classification(status),
        "detail": detail,
    }


def _one_pin(pin: dict, fetch: Fetch) -> dict:
    url = str(pin.get("url") or "")
    expected = str(pin.get("content_sha256") or "")
    label = url or str(pin.get("id") or "pin")
    if not url or not expected:
        return _drift_row(label, "error", f"incomplete pin {label}")
    try:
        status, body = fetch(url)
    except Exception as exc:
        return _drift_row(label, "error", f"withheld network for {label}: {exc}")
    if status is None:
        return _drift_row(label, "error", f"withheld network for {label}")
    if int(status) >= 500:
        return _drift_row(
            label,
            "skip-with-warning",
            f"HTTP {status} for {label}; update is unknown, not a pass",
        )
    if int(status) != 200:
        return _drift_row(label, "error", f"HTTP {status} for {label}")
    actual = hashlib.sha256(body).hexdigest()
    if actual != expected:
        return _drift_row(label, "fail", f"docs drift for {label}: update the fixture")
    return _drift_row(label, "pass", f"unchanged {label}")


def check_tool_layouts(tree: Path, fixture: dict | None = None) -> dict[str, list[str]]:
    """Layout errors for Claude Code, Codex, Gemini CLI, Cursor, and Grok."""
    spec = fixture if fixture is not None else load_fixture()
    tools = spec.get("tools") or {}
    found: dict[str, list[str]] = {}
    for tool in TOOL_IDS:
        tool_spec = tools.get(tool)
        if not isinstance(tool_spec, dict):
            found[tool] = [f"missing pin for {tool}"]
            continue
        found[tool] = check_layout(tree, tool_spec)
    return found


def _example_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def published_example_findings(pages_dir: Path, fixture: dict | None = None) -> list[str]:
    """Fail or warn when a tool-page example disagrees with its pin.

    A wrong entry filename fails. A config key the pin does not allow warns.
    """
    spec = fixture if fixture is not None else load_fixture()
    findings: list[str] = []
    pages = Path(pages_dir)
    for tool in TOOL_IDS:
        page = pages / f"{tool}.md"
        if not page.is_file():
            findings.append(f"fail: missing tool page {tool}.md")
            continue
        text = page.read_text(encoding="utf-8")
        match = EXAMPLE_BLOCK.search(text)
        if match is None or match.group(1) != tool:
            findings.append(f"fail: {tool}.md has no host-doc example")
            continue
        fields = _example_fields(match.group(2))
        tool_spec = spec.get("tools", {}).get(tool) or {}
        forbidden = set(spec.get("forbidden_filenames", [])) | set(tool_spec.get("forbidden_filenames", []))
        required = list(tool_spec.get("required_paths", []))
        entry = fields.get("entry", "")
        if not entry or entry in forbidden or (required and entry not in required):
            findings.append(f"fail: {tool}.md example entry {entry or '(blank)'} disagrees with the pin")
        for relative in [item.strip() for item in fields.get("paths", "").split(",") if item.strip()]:
            if relative in forbidden or Path(relative).name in forbidden:
                findings.append(f"fail: {tool}.md example path {relative} disagrees with the pin")
        allowed: set[str] = set()
        for cfg in (tool_spec.get("config_files") or {}).values():
            if isinstance(cfg, dict):
                allowed.update(str(key) for key in cfg.get("keys", []))
                allowed.update(f"context.{key}" for key in cfg.get("context_keys", []))
        for key in [item.strip() for item in fields.get("config_keys", "").split(",") if item.strip()]:
            if key not in allowed:
                findings.append(f"warn: {tool}.md example config key {key} is not in the pin")
    return findings


def ledger_check_status(check: dict) -> str:
    """Pass only a check that ran and was measured. Otherwise skipped or unknown."""
    if not isinstance(check, dict):
        return "unknown"
    if check.get("ran") is False or str(check.get("status") or "").casefold() in {"skipped", "skip"}:
        return "skipped"
    if check.get("measured") is not True or check.get("ran") is not True:
        return "unknown"
    outcome = str(check.get("status") or "").casefold()
    if outcome == "pass" or check.get("ok") is True:
        return "pass"
    if outcome == "fail" or check.get("ok") is False:
        return "fail"
    return "unknown"


def score_golden_ledger(checks: list[dict]) -> dict:
    """Overall status. An unmeasured or skipped check cannot make the ledger a pass."""
    rows = [
        {"id": str(check.get("id") or ""), "status": ledger_check_status(check)}
        for check in checks
    ]
    statuses = [row["status"] for row in rows]
    if not statuses or any(item == "unknown" for item in statuses):
        overall = "unknown"
    elif any(item == "fail" for item in statuses):
        overall = "fail"
    elif any(item == "skipped" for item in statuses):
        overall = "skipped"
    else:
        overall = "pass"
    return {"checks": rows, "overall": overall}


def load_golden_corpus(path: Path | None = None) -> dict:
    return json.loads((path or GOLDEN_CORPUS).read_text(encoding="utf-8"))


def run_golden_task(task: dict) -> dict:
    """Score one corpus task from its recorded checks. No model and no vendor CLI."""
    checks = task.get("checks") if isinstance(task, dict) else None
    return score_golden_ledger(list(checks or []))


def _urlopen_fetch(url: str) -> tuple[int, bytes]:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # nosec B310 - pinned docs URL
            status = getattr(response, "status", 200)
            return int(status), response.read()
    except urllib.error.HTTPError as exc:
        payload = exc.read() if exc.fp else b""
        return int(exc.code), payload
    except urllib.error.URLError as exc:
        raise ConnectionError(str(exc.reason)) from exc


def main(argv: list[str] | None = None) -> int:
    """Opt-in docs drift fetch. Exit 0 only when every pin passes."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--check-docs-drift" not in args:
        print("usage: python3 conformance.py --check-docs-drift", file=sys.stderr)
        return 2
    fixture = load_fixture()
    results = check_docs_drift(list(fixture.get("pins", [])), _urlopen_fetch)
    for item in results:
        print(f"{item['status']}: {item['pin']}: {item['detail']}")
    if results and all(item["status"] == "pass" for item in results):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
