"""Hooks and store refresh use the installer-recorded tool, not PATH."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GreenlitStoreToolTest(unittest.TestCase):
    def test_store_tool_uses_the_recorded_path_when_path_is_older(self):
        stores = _load("stores_greenlit", ROOT / "runtime" / "stores.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorded = root / "recorded" / "mempalace"
            older = root / "path" / "mempalace"
            recorded.parent.mkdir()
            older.parent.mkdir()
            recorded.write_text("#!/bin/sh\n", encoding="utf-8")
            older.write_text("#!/bin/sh\n", encoding="utf-8")
            recorded.chmod(0o755)
            user = root / "user"
            user.mkdir()
            (user / "user.properties").write_text(f"mempalace={recorded}\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"CHAOS_ENGINE_USER_DIR": str(user)}):
                with mock.patch.object(stores.shutil, "which", return_value=str(older)):
                    chosen = stores._store_tool("mempalace")
        self.assertEqual(str(recorded), chosen)

    def test_store_argv_is_cross_platform_for_a_cmd_launcher(self):
        stores = _load("stores_greenlit_argv", ROOT / "runtime" / "stores.py")
        with mock.patch.object(stores.os, "name", "nt"):
            argv = stores._store_argv(r"C:\Users\a\graphify.cmd", ["extract", "."])
        self.assertEqual(["cmd", "/c", r"C:\Users\a\graphify.cmd", "extract", "."], argv)
