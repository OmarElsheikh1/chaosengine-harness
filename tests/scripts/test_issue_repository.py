"""Harness defects stay on chaosengine-harness. SHAFT_ENGINE defects stay there."""

from __future__ import annotations

import unittest

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))  # noqa: E402

from runtime.issue_repository import (  # noqa: E402
    HARNESS_REPO,
    SHAFT_REPO,
    choose_issue_repository,
)


class IssueRepositoryTest(unittest.TestCase):
    def test_harness_defect_stays_on_the_harness_repo(self):
        self.assertEqual(
            HARNESS_REPO,
            choose_issue_repository(
                "open an issue for the chaosengine harness: Grok hooks stay disabled"
            ),
        )

    def test_shaft_product_defect_stays_on_shaft_engine(self):
        self.assertEqual(
            SHAFT_REPO,
            choose_issue_repository("SHAFT_ENGINE assertion failed in BrowserActions"),
        )

    def test_vendored_tree_does_not_move_a_harness_defect(self):
        self.assertEqual(
            HARNESS_REPO,
            choose_issue_repository(
                "ChaosEngine hooks are broken; file it on SHAFT_ENGINE "
                "because chaos-engine is vendored there"
            ),
        )

    def test_shaft_defect_is_not_filed_on_the_harness(self):
        self.assertEqual(
            SHAFT_REPO,
            choose_issue_repository(
                "file a SHAFT_ENGINE bug on chaosengine-harness"
            ),
        )

    def test_both_products_and_neither_fail_closed(self):
        with self.assertRaises(ValueError):
            choose_issue_repository(
                "chaos-engine doctor fails and SHAFT_ENGINE clicks fail"
            )
        with self.assertRaises(ValueError):
            choose_issue_repository("it is broken")


if __name__ == "__main__":
    unittest.main()
