"""Issue 32 per-file sync, kept edits, and a truncated curl|bash guard."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _bootstrap():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("ce_bootstrap_sync", root / "bootstrap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlanSyncTest(unittest.TestCase):
    def test_truncated_curl_bash_and_foreign_edit_are_preserved_or_refused(self):
        boot = _bootstrap()
        remote = {"owned.txt": {"sha256": "a" * 64, "gitBlobSha1": "b" * 40, "size": 1, "mode": "100644"}}
        base = {"owned.txt": "c" * 64}
        local = {"owned.txt": "d" * 64}
        actions = {row["path"]: row["action"] for row in boot.plan_file_actions(remote, base, local)}
        self.assertEqual("edited", actions["owned.txt"])
        script = (Path(__file__).resolve().parents[2] / "install.sh").read_text(encoding="utf-8")
        self.assertIn('main "$@"', script)
        body = script.splitlines()
        while body and not body[-1].strip():
            body.pop()
        self.assertTrue(body[-1].startswith("main "))
        truncated = "\n".join(body[:-1]) + "\n"
        import os
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "install.sh"
            path.write_text(truncated, encoding="utf-8")
            path.chmod(0o755)
            completed = subprocess.run(
                ["sh", str(path)],
                cwd=temporary,
                env={**os.environ, "CHAOS_ENGINE_RESOLVE_ONLY": "1"},
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(0, completed.returncode)
        self.assertEqual("", completed.stdout)
        self.assertEqual("", completed.stderr)
