"""VERSION-bump gate ported from SHAFT test_ce_retro_2026_10_31_6.VersionBumpGateTest.

Paths are harness-root paths: this tree is the harness, not a chaos-engine/ subtree.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class VersionBumpGateTest(unittest.TestCase):
    def test_requires_version_when_harness_changes(self) -> None:
        from scripts.ci.overlay_pre_push import ce_version_bump_failures

        hits = ce_version_bump_failures(ROOT, ["references/bot-entry.md"])
        self.assertTrue(hits)
        self.assertIn("ce-version-bump", hits[0])

    def test_pass_when_version_in_paths(self) -> None:
        from scripts.ci.overlay_pre_push import ce_version_bump_failures

        hits = ce_version_bump_failures(
            ROOT,
            ["references/bot-entry.md", "VERSION"],
        )
        self.assertEqual([], hits)


if __name__ == "__main__":
    unittest.main()
