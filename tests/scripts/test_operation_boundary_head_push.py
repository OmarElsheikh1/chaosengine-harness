"""HEAD refspecs follow the branch checked out in the directory that is pushing.

Issue #73: a linked worktree was denied ``git push origin HEAD:<its-branch>``
because rev-parse ran in the hook root, which was still on ``main``.
"""

from __future__ import annotations

import importlib.util
import os
import shlex
import subprocess  # nosec B404 - git init and worktree add on a temp fixture.
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRANCH = "ChaosEngine/installer-scenarios"


def load_boundary():
    script = ROOT / "rules" / "operation_boundary.py"
    spec = importlib.util.spec_from_file_location("ce_operation_boundary_head_push", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str) -> None:
    subprocess.run(  # nosec B603 B607 - fixed git argv on a temp fixture, no shell.
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=Tester", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


class HeadPushWorktreeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(os.chdir, Path.cwd())
        self.hook = Path(self.temporary.name) / "hook"
        self.hook.mkdir()
        git(self.hook, "init", "-q", "-b", "main")
        readme = self.hook / "README"
        readme.write_text("x\n", encoding="utf-8")
        git(self.hook, "add", "README")
        git(self.hook, "commit", "-q", "-m", "init")
        self.work = Path(self.temporary.name) / "wt"
        git(self.hook, "worktree", "add", "-q", "-b", BRANCH, str(self.work), "HEAD")
        self.boundary = load_boundary()
        os.chdir(self.hook)

    def test_head_push_uses_the_branch_checked_out_in_the_pushing_directory(self):
        os.chdir(self.work)
        allowed = f"git push origin HEAD:{BRANCH}"
        denied = "git push origin HEAD:main"
        self.assertIsNone(self.boundary.head_destination_block(self.hook, allowed))
        self.assertEqual(
            "head-destination-mismatch",
            self.boundary.head_destination_block(self.hook, denied),
        )
        os.chdir(self.hook)
        self.assertIsNone(self.boundary.head_destination_block(self.hook, denied))
        self.assertEqual(
            "head-destination-mismatch",
            self.boundary.head_destination_block(self.hook, allowed),
        )

    def test_leading_literal_directory_selects_the_worktree_without_chdir(self):
        self.assertEqual(self.hook.resolve(), Path.cwd().resolve())
        work = shlex.quote(str(self.work))
        hook = shlex.quote(str(self.hook))
        allowed = f"cd {work} && git push origin HEAD:{BRANCH}"
        denied = f"cd {work} && git push origin HEAD:main"
        self.assertIsNone(self.boundary.head_destination_block(self.hook, allowed))
        self.assertEqual(
            "head-destination-mismatch",
            self.boundary.head_destination_block(self.hook, denied),
        )
        repeated = f"cd {work} && cd {hook} && git push origin HEAD:{BRANCH}"
        self.assertEqual(
            "head-destination-mismatch",
            self.boundary.head_destination_block(self.hook, repeated),
        )
        twice = f"cd {work} && cd {work} && git push origin HEAD:{BRANCH}"
        self.assertEqual(
            "head-destination-mismatch",
            self.boundary.head_destination_block(self.hook, twice),
        )
        powershell = f"Set-Location {work}; git push origin HEAD:{BRANCH}"
        self.assertIsNone(self.boundary.head_destination_block(self.hook, powershell))
        pushed = f"Push-Location {work}; git push origin HEAD:{BRANCH}"
        self.assertIsNone(self.boundary.head_destination_block(self.hook, pushed))
        self.assertIsNone(
            self.boundary.head_destination_block(self.hook, "cd $WT && git push origin HEAD:main")
        )
        dynamic = f"cd $WT && git push origin HEAD:{BRANCH}"
        self.assertEqual(
            "head-destination-mismatch",
            self.boundary.head_destination_block(self.hook, dynamic),
        )

    def test_directory_change_after_the_push_keeps_the_worktree_cwd(self):
        previous = Path.cwd()
        os.chdir(self.work)
        try:
            self.assertEqual(
                "head-destination-mismatch",
                self.boundary.head_destination_block(
                    self.hook, "git push origin HEAD:main && cd /tmp"
                ),
            )
            self.assertIsNone(
                self.boundary.head_destination_block(
                    self.hook, f"git push origin HEAD:{BRANCH} && cd /tmp"
                ),
            )
        finally:
            os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
