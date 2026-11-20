"""Doctor JSON and the retrieve store list omit a removed transcript store."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
REMOVED = "de" + "ja"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RemovedStoreAbsenceTest(unittest.TestCase):
    def test_doctor_report_and_retrieve_stores_omit_removed_store(self):
        retrieve = _load("ce_retrieve_absent", ROOT / "runtime" / "retrieve.py")
        install = _load("ce_install_absent", ROOT / "install.py")
        self.assertNotIn(REMOVED, retrieve.STORES)
        self.assertNotIn(REMOVED, install.CAPABILITY_COMPONENTS)
        self.assertNotIn(REMOVED, install.legacy_capability_policy())
        self.assertNotIn(REMOVED, install.default_bundle_options())
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            install.install_with_dependencies(
                project, ROOT, "b" * 40, provisioner=lambda *_args: None
            )
            doctor = install.doctor_with_dependencies(project, verify_clients=False)
        self.assertNotIn(REMOVED, doctor["components"])
        self.assertTrue(all(REMOVED not in str(name) for name in doctor["components"]))

    def test_unknown_store_fails_closed_without_launching(self):
        retrieve = _load("ce_retrieve_absent_cli", ROOT / "runtime" / "retrieve.py")
        launched: list[object] = []

        def refuse(*args, **kwargs):
            launched.append(args)
            raise AssertionError("launched")

        stderr = io.StringIO()
        with mock.patch.object(retrieve.subprocess, "run", refuse), mock.patch.object(
            sys, "stderr", stderr
        ):
            code = retrieve.main(["--store", REMOVED, "what happened"])
        self.assertEqual(2, code)
        self.assertEqual([], launched)
        self.assertIn(f"unknown-store: {REMOVED}", stderr.getvalue())

    def test_upgrade_strips_retired_mcp_then_drops_the_list(self):
        policy = _load("ce_mcp_absent", ROOT / "runtime" / "mcp_policy.py")
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            mcp = project / ".mcp.json"
            mcp.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            REMOVED: {"command": REMOVED},
                            "keep": {"command": "k"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            removed = policy.upgrade_strip_retired_mcp(project)
            data = json.loads(mcp.read_text(encoding="utf-8"))
        self.assertEqual([REMOVED], removed)
        self.assertNotIn(REMOVED, data["mcpServers"])
        self.assertEqual({"command": "k"}, data["mcpServers"]["keep"])
        self.assertEqual([], policy._RETIRED_MCP_STRIP)

    def test_removed_flag_is_unknown(self):
        install = _load("ce_install_absent_flag", ROOT / "install.py")
        with self.assertRaises(SystemExit) as raised:
            install.parser().parse_args(["install", "--project", ".", "--with-" + REMOVED])
        self.assertEqual(2, raised.exception.code)
        with self.assertRaises(SystemExit):
            install.parser().parse_args(["repair", "--project", ".", "--component", REMOVED])


if __name__ == "__main__":
    unittest.main()
