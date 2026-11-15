"""Offline host-doc layout and docs-drift checks.

Reads a fixture tree and pinned hashes. Does not start a vendor CLI and does
not call a model API. A withheld network or HTTP 5xx is an error or a
skip-with-warning, never a pass. Live multi-model runs stay future.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Callable

FIXTURE = Path(__file__).resolve().parent / "evals" / "host-doc-conformance.json"
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
    rules = root / spec.get("cursor_rules_dir", ".cursor/rules")
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


def _one_pin(pin: dict, fetch: Fetch) -> dict:
    url = str(pin.get("url") or "")
    expected = str(pin.get("content_sha256") or "")
    label = url or str(pin.get("id") or "pin")
    if not url or not expected:
        return {"pin": label, "status": "error", "detail": f"incomplete pin {label}"}
    try:
        status, body = fetch(url)
    except Exception as exc:
        return {
            "pin": label,
            "status": "error",
            "detail": f"withheld network for {label}: {exc}",
        }
    if status is None:
        return {"pin": label, "status": "error", "detail": f"withheld network for {label}"}
    if int(status) >= 500:
        return {
            "pin": label,
            "status": "skip-with-warning",
            "detail": f"HTTP {status} for {label}; update is unknown, not a pass",
        }
    if int(status) != 200:
        return {"pin": label, "status": "error", "detail": f"HTTP {status} for {label}"}
    actual = hashlib.sha256(body).hexdigest()
    if actual != expected:
        return {
            "pin": label,
            "status": "fail",
            "detail": f"docs drift for {label}: update the fixture",
        }
    return {"pin": label, "status": "pass", "detail": f"unchanged {label}"}


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
