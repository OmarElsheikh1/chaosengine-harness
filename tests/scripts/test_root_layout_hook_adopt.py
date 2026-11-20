"""A root-layout primary adopts delegate hooks into the linked worktree."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))
import hosts  # noqa: E402


def load(path: Path, name: str):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _root_overlay_candidate(command: str) -> str:
    """Locator text with the two nested overlay paths removed."""
    return command.replace(".chaos-engine/worktree_overlay.py", "").replace(
        "chaos-engine/worktree_overlay.py", ""
    )


class RootLayoutHookAdoptTest(unittest.TestCase):
    def test_root_layout_adopt_copies_regular_hooks_and_locator_sees_root(self):
        for windows, host in ((False, "codex"), (True, "copilot"), (True, "grok")):
            command = hosts.chaos_guard_locator_command(windows=windows, host=host, event="SessionStart")
            # Nested paths also contain this filename. A root candidate remains
            # after those two strings are removed; the two-path locator does not.
            self.assertIn("worktree_overlay.py", _root_overlay_candidate(command))
            if windows:
                self.assertIn("'worktree_overlay.py'", command)
            else:
                self.assertIn("for n in .chaos-engine chaos-engine .;do", command)
        overlay = load(ROOT / "runtime" / "worktree_overlay.py", "ce_root_layout_adopt")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            primary = base / "primary"
            primary.mkdir()
            self.assertFalse((primary / "chaos-engine").exists())
            self.assertFalse((primary / ".chaos-engine" / "hooks").exists())
            shutil.copy2(ROOT / "runtime" / "worktree_overlay.py", primary / "worktree_overlay.py")
            hooks = primary / "hooks"
            hooks.mkdir()
            for path in (ROOT / "hooks").iterdir():
                if path.is_file():
                    shutil.copy2(path, hooks / path.name)
            shutil.copy2(ROOT / "runtime" / "session_token_usage.py", primary / "session_token_usage.py")
            shutil.copy2(ROOT / ".gitignore", primary / ".gitignore")
            self._git(primary, "init", "-q")
            self._git(primary, "add", ".gitignore", "worktree_overlay.py", "session_token_usage.py", "hooks")
            self._git(primary, "commit", "-q", "-m", "root layout")
            session = base / "session"
            self._git(primary, "worktree", "add", "-q", str(session))
            self.assertFalse((session / "chaos-engine").exists())
            self.assertFalse((session / ".chaos-engine" / "hooks").exists())
            ignored = subprocess.run(  # nosec B603 B607 - fixed git check-ignore.
                ["git", "check-ignore", "-q", ".chaos-engine/hooks/launch.py"],
                cwd=session,
                check=False,
            )
            self.assertEqual(0, ignored.returncode)
            completed = subprocess.run(  # nosec B603 - shipped overlay adopt.
                [sys.executable, str(primary / "worktree_overlay.py"), "adopt"],
                cwd=session,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            copied = session / ".chaos-engine" / "hooks" / "launch.py"
            self.assertTrue(copied.is_file())
            self.assertFalse(copied.is_symlink())
            self.assertTrue(stat_regular(copied))
            self.assertEqual((primary / "hooks" / "launch.py").read_bytes(), copied.read_bytes())
            for name in overlay._REQUIRED_DELEGATE_HOOKS:
                path = session / ".chaos-engine" / "hooks" / name
                self.assertFalse(path.is_symlink(), name)
                self.assertEqual((primary / "hooks" / name).read_bytes(), path.read_bytes(), name)

    def test_root_layout_adopt_rejects_a_symlink_primary_hook(self):
        overlay = load(ROOT / "runtime" / "worktree_overlay.py", "ce_root_layout_symlink")
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            primary = base / "primary"
            hooks = primary / "hooks"
            hooks.mkdir(parents=True)
            for name in overlay._REQUIRED_DELEGATE_HOOKS:
                (hooks / name).write_text(f"print({name!r})\n", encoding="utf-8")
            outside = base / "outside.py"
            outside.write_text("print('linked')\n", encoding="utf-8")
            launch = hooks / "launch.py"
            launch.unlink()
            launch.symlink_to(outside)
            (primary / "session_token_usage.py").write_text("TOKEN = 'root'\n", encoding="utf-8")
            (primary / "worktree_overlay.py").write_text("# root\n", encoding="utf-8")
            session = base / "session"
            session.mkdir()
            with self.assertRaises(RuntimeError) as raised:
                overlay.ensure_delegate_hooks(primary, session)
            self.assertIn("symlink", str(raised.exception))
            self.assertFalse((session / ".chaos-engine" / "hooks" / "launch.py").exists())

    def _git(self, cwd: Path, *args: str) -> None:
        subprocess.run(  # nosec B603 - fixed git argv in a temp repo.
            ["git", "-c", "user.name=Root Layout", "-c", "user.email=root-layout@example.com", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_CONFIG_COUNT": "0"},
        )


def stat_regular(path: Path) -> bool:
    import stat
    return stat.S_ISREG(path.lstat().st_mode)


if __name__ == "__main__":
    unittest.main()
