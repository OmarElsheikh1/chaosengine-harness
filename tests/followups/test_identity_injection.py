"""Identity body reaches SessionStart, including Claude after compaction."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "guard.py"
TRUTH = """<!-- CHAOSENGINE-IDENTITY-TRUTH:START -->
## Truth

- Speak unabridged truth: do not lie, hide, skew, manipulate, or omit material facts.
- Prefer evidence over inference; say what you know and what you do not.
- When uncertain, say so plainly; never pad confidence.
<!-- CHAOSENGINE-IDENTITY-TRUTH:END -->"""
STEP_BACK = (
    "- Step back: before work, name the real goal and ask whether a better approach, "
    "tool, or model exists; after two failed attempts on one approach, stop patching, "
    "widen the search, re-plan, and push back with the better option "
    "([why](references/identity-step-back.md))."
)


def _lifecycle():
    name = "identity_injection_lifecycle"
    spec = importlib.util.spec_from_file_location(name, ROOT / "hooks" / "lifecycle.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _hook(host: str, event_name: str, source: str | None = None) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temporary:
        event = {
            "hook_event_name": event_name,
            "session_id": f"identity-{host}-{event_name}",
            "cwd": temporary,
        }
        if source is not None:
            event["source"] = source
        env = {
            **os.environ,
            "CHAOS_ENGINE_HOST": host,
            "CHAOS_ENGINE_STORE_REFRESH": "0",
            "CHAOS_ENGINE_PROTECTED_CHECKOUTS": str(ROOT),
        }
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            check=False,
            env=env,
            cwd=temporary,
        )


def _payload(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _specific(payload: dict) -> dict:
    specific = payload.get("hookSpecificOutput")
    assert isinstance(specific, dict), payload
    return specific


def test_claude_session_start_nests_the_identity_body():
    payload = _payload(_hook("claude", "SessionStart", source="startup"))
    specific = _specific(payload)
    assert specific["hookEventName"] == "SessionStart"
    assert "Speak unabridged truth" in specific["additionalContext"]
    assert "Step back" in specific["additionalContext"]
    assert "additionalContext" not in payload


def test_claude_compact_session_start_reinjects_the_identity_body():
    payload = _payload(_hook("claude", "SessionStart", source="compact"))
    specific = _specific(payload)
    assert specific["hookEventName"] == "SessionStart"
    assert "Speak unabridged truth" in specific["additionalContext"]
    assert "Step back" in specific["additionalContext"]
    assert "additionalContext" not in payload


def test_claude_subagent_start_keeps_the_native_event_name():
    payload = _payload(_hook("claude", "SubagentStart"))
    specific = _specific(payload)
    assert specific["hookEventName"] == "SubagentStart"
    assert "Speak unabridged truth" in specific["additionalContext"]
    assert "Step back" in specific["additionalContext"]
    assert "additionalContext" not in payload


def test_codex_session_start_keeps_its_shape_and_includes_the_body():
    payload = _payload(_hook("codex", "SessionStart", source="startup"))
    specific = _specific(payload)
    assert specific["hookEventName"] == "SessionStart"
    assert "Speak unabridged truth" in specific["additionalContext"]
    assert "Step back" in specific["additionalContext"]
    assert "additionalContext" not in payload


def test_missing_identity_file_falls_back_to_the_locator(tmp_path, monkeypatch):
    lifecycle = _lifecycle()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lifecycle, "_search_roots", lambda: [tmp_path])
    text = lifecycle.session_start_context(None, "active")
    assert "Identity: `.chaos-engine/identity.md`" in text.splitlines()
    assert "Speak unabridged truth" not in text
    assert "Step back" not in text


def test_identity_keeps_the_truth_block_and_adds_step_back():
    text = (ROOT / "identity.md").read_text(encoding="utf-8")
    assert TRUTH in text
    assert STEP_BACK in text
    lean = text.index("Lean engineer:")
    step = text.index("Step back:")
    peer = text.index("- Peer:")
    assert lean < step < peer
    assert (ROOT / "references" / "identity-step-back.md").is_file()
    harness_map = (ROOT / "references" / "harness-map.md").read_text(encoding="utf-8")
    assert "`references/identity-step-back.md`" in harness_map
