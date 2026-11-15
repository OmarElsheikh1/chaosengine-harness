"""A worktree hook adopt must copy session_token_usage.py or every tool call is blocked."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


class DelegateSessionTokenTests(unittest.TestCase):
    def test_adopt_copies_session_token_usage_and_pretool_does_not_crash(self):
        overlay = load(ROOT / "worktree_overlay.py", "ce_delegate_overlay_token")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            primary = base / "primary"
            hooks = primary / ".chaos-engine" / "hooks"
            hooks.mkdir(parents=True)
            for path in (ROOT / "hooks").iterdir():
                if path.is_file():
                    shutil.copy2(path, hooks / path.name)
            source = ROOT / "session_token_usage.py"
            shutil.copy2(source, primary / ".chaos-engine" / "session_token_usage.py")
            session = base / "session"
            session.mkdir()
            overlay.ensure_delegate_hooks(primary, session)
            copied = session / ".chaos-engine" / "session_token_usage.py"
            self.assertTrue(copied.is_file())
            self.assertFalse(copied.is_symlink())
            self.assertEqual(source.read_bytes(), copied.read_bytes())
            kernel = load(session / ".chaos-engine" / "hooks" / "kernel.py", "ce_delegate_kernel_token")
            event = kernel.normalize_event(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "delegate-session-token",
                    "cwd": str(session),
                    "tool_name": "read_file",
                    "tool_input": {"target_file": "VERSION"},
                },
                "grok",
            )
            report = kernel.evaluate(event)
        self.assertNotEqual("deny", report.decision)
        rendered = json.dumps(report.to_dict())
        self.assertNotIn("invalid JSON", rendered)

    def test_adopt_rejects_a_symlinked_session_token_usage(self):
        overlay = load(ROOT / "worktree_overlay.py", "ce_delegate_overlay_symlink")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            primary = base / "primary"
            hooks = primary / ".chaos-engine" / "hooks"
            hooks.mkdir(parents=True)
            for path in (ROOT / "hooks").iterdir():
                if path.is_file():
                    shutil.copy2(path, hooks / path.name)
            outside = base / "outside.py"
            outside.write_text("TOKEN = 'from-symlink'\n", encoding="utf-8")
            link = primary / ".chaos-engine" / "session_token_usage.py"
            link.symlink_to(outside)
            session = base / "session"
            session.mkdir()
            with self.assertRaises(RuntimeError) as raised:
                overlay.ensure_delegate_hooks(primary, session)
            self.assertIn("symlink", str(raised.exception))
            self.assertFalse((session / ".chaos-engine" / "session_token_usage.py").exists())


if __name__ == "__main__":
    unittest.main()
