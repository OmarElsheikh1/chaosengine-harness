"""ChaosEngine VERSION + upgrade broadcast string (ported from SHAFT #8057)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOD = ROOT / "scripts/ci/ce_version.py"


def _load():
    spec = importlib.util.spec_from_file_location("ce_version", MOD)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class CeVersionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load()

    def test_repo_version_readable(self) -> None:
        value = self.mod.read_version()
        self.assertRegex(value, r"^\d+\.[1-4]\.\d{8}\.[1-9]\d*$")
        self.assertEqual(f"CE upgrade {value}", self.mod.upgrade_broadcast())
        self.assertEqual(value, (ROOT / "VERSION").read_text(encoding="utf-8").strip())

    def test_scheme_keys_and_next(self) -> None:
        key = self.mod.version_key
        self.assertGreater(key("0.4.20261102.1"), key("2026.10.31.13"))
        self.assertGreater(key("0.4.20261102.2"), key("0.4.20261102.1"))
        self.assertEqual("0.4.20261102.1", self.mod.next_version("2026.10.31.13", "2026-11-02"))
        self.assertEqual("0.4.20261102.2", self.mod.next_version("0.4.20261102.1", "2026-11-02"))
        self.assertEqual("0.4.20261103.1", self.mod.next_version("0.4.20261102.5", "2026-11-03"))
        with self.assertRaises(ValueError):
            self.mod.next_version("0.4.20261102.1", "2026-11-01")

    def test_quarter_rollover_orders_by_date(self) -> None:
        """Q4 to Q1 and Q1 to Q2 compare by date, not by the quarter digit."""
        key = self.mod.version_key
        self.assertLess(key("0.4.20261231.1"), key("0.1.20270101.1"))
        self.assertLess(key("0.4.20261231.9"), key("0.1.20270101.1"))
        self.assertLess(key("0.1.20260331.1"), key("0.2.20260401.1"))
        self.assertEqual("0.1.20270101.1", self.mod.next_version("0.4.20261231.3", "2027-01-01"))
        self.assertEqual("0.2.20260401.1", self.mod.next_version("0.1.20260331.2", "2026-04-01"))
        with self.assertRaises(ValueError):
            key("0.1.20261231.1")

    def test_invalid_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "VERSION"
            bad.write_text("not-a-version\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                self.mod.read_version(bad)

    def test_check_cli_against_real_version_file(self) -> None:
        self.assertEqual(0, self.mod.main(["check"]))
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tool.py"), "ce-version", "check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("ce_version: pass", completed.stdout)

    def test_concurrent_bump_rule_names_next_version(self) -> None:
        doc = (ROOT / "references/ce-upgrade-on-release.md").read_text(encoding="utf-8")
        self.assertIn("Concurrent bumps", doc)
        self.assertIn("merges second", doc)
        self.assertIn("next_version", doc)


class ChaosEngineVersionFloorTest(unittest.TestCase):
    """Dependabot floor: harness VERSION stays at or above 2026.10.31.12."""

    def test_version_at_least_2026_10_31_12(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        mod = _load()
        self.assertGreaterEqual(mod.version_key(version), mod.version_key("2026.10.31.12"))


if __name__ == "__main__":
    unittest.main()
