"""A forwarding shim named chaos-engine/ is not policy SOURCE."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name: str):
    path = ROOT / name
    if not path.is_file() and "/" not in name:
        nested = ROOT / "runtime" / name
        if nested.is_file():
            path = nested
    specification = importlib.util.spec_from_file_location(name.replace(".", "_"), path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def plant_overlay(project: Path, skill: str) -> None:
    overlay = project / ".chaos-engine"
    (overlay / "skills/chaos-engine").mkdir(parents=True)
    (overlay / "skills/chaos-engine/SKILL.md").write_text(skill, encoding="utf-8")
    (overlay / "hooks").mkdir()
    (overlay / "hooks/guard.py").write_text("hook\n", encoding="utf-8")
    (overlay / "identity.md").write_text("identity\n", encoding="utf-8")


def plant_shim(project: Path) -> None:
    shim = project / "chaos-engine"
    shim.mkdir()
    (shim / "README.md").write_text("moved\n", encoding="utf-8")
    (shim / "install.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    cache = shim / "skills/colibri/scripts/__pycache__"
    cache.mkdir(parents=True)
    (cache / "probe.cpython-312.pyc").write_bytes(b"pyc")


class PolicyOverlayForwardingShimTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay = load("overlay_match.py")
        cls.install = load("install.py")

    def test_shim_policy_files_do_not_fail_doctor(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            plant_shim(project)
            plant_overlay(project, "portable router\n")
            mismatches = self.overlay.policy_hash_mismatches(
                project / "chaos-engine", project / ".chaos-engine"
            )
            self.assertIn("skills/chaos-engine/SKILL.md", mismatches)
            result = {"status": "healthy", "components": {}}
            self.overlay.apply_policy_hash_doctor(result, project)
            self.assertEqual("healthy", result["status"])
            row = result["components"]["policy-overlay"]
            self.assertEqual("healthy", row["status"])
            self.assertEqual("not-a-repository-checkout", row["reason"])

    def test_repository_checkout_still_reports_policy_drift(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            plant_shim(project)
            plant_overlay(project, "portable router\n")
            source_skill = project / "chaos-engine/skills/chaos-engine"
            source_skill.mkdir(parents=True)
            (source_skill / "SKILL.md").write_text("older router\n", encoding="utf-8")
            result = {"status": "healthy", "components": {}}
            self.overlay.apply_policy_hash_doctor(result, project)
            self.assertEqual("recovery-required", result["status"])
            self.assertEqual(
                "recovery-required", result["components"]["policy-overlay"]["status"]
            )
            self.assertEqual("policy hash drift", result["components"]["policy-overlay"]["reason"])

    def test_shim_repair_does_not_ask_for_the_one_liner(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            plant_shim(project)
            plant_overlay(project, "portable router\n")
            repaired = self.install.repair_component(project, "policy-overlay")
            self.assertEqual("repaired", repaired["status"])
            self.assertEqual("not-a-repository-checkout", repaired["action"])

    def test_shim_nested_overlay_still_repairs(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            plant_shim(project)
            plant_overlay(project, "portable router\n")
            nested = project / ".chaos-engine/.chaos-engine/skills/chaos-engine"
            nested.mkdir(parents=True)
            (nested / "SKILL.md").write_text("stale router\n", encoding="utf-8")
            (project / ".chaos-engine/identity.md").write_text("identity\n", encoding="utf-8")
            nested_identity = project / ".chaos-engine/.chaos-engine/identity.md"
            nested_identity.write_text("other identity\n", encoding="utf-8")
            result = {"status": "healthy", "components": {}}
            self.overlay.apply_policy_hash_doctor(result, project)
            self.assertEqual("recovery-required", result["status"])
            repaired = self.install.repair_component(project, "policy-overlay")
            self.assertEqual("removed-nested-overlay", repaired["action"])
            self.assertFalse((project / ".chaos-engine/.chaos-engine").exists())


if __name__ == "__main__":
    unittest.main()
