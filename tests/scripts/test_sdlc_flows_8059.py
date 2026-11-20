"""Role SDLC gates (#8059) and cited capability caps (#8053)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))

import capability_profile  # noqa: E402
import sdlc_flows  # noqa: E402

READY_STORY = {
    "intent": "A payer sees the recorded balance.",
    "criteria": ["Balance shows a currency amount"],
    "problems": ["balance"],
}
FIXTURE_CAP = """
| id | hard_cap_bytes | source |
| --- | --- | --- |
| fixture-host | 32768 | https://example.invalid/project-docs |
| open-host | unknown | hooks/kernel.py |
"""


class SdlcFlowsTest(unittest.TestCase):
    def test_missing_criteria_is_not_ready(self):
        result = sdlc_flows.ready_gate(
            {"intent": "see the balance", "criteria": [], "problems": ["balance"]}
        )
        self.assertFalse(result["ready"])
        self.assertIn("missing-criteria", result["reasons"])

    def test_untestable_criterion_is_not_ready(self):
        result = sdlc_flows.ready_gate(
            {
                "intent": "see the balance",
                "criteria": ["make it nice"],
                "problems": ["balance"],
            }
        )
        self.assertFalse(result["ready"])
        self.assertIn("untestable-criteria", result["reasons"])

    def test_two_problems_fail_refinement(self):
        result = sdlc_flows.refine(
            {
                "intent": "pay and redesign",
                "criteria": ["A recorded payment id is returned"],
                "problems": ["pay", "redesign"],
            }
        )
        self.assertFalse(result["ready"])
        self.assertIn("mixed-problems", result["reasons"])

    def test_passing_but_contradicting_check_fails_intent_match(self):
        result = sdlc_flows.intent_match(
            criteria=["A recorded payment id is returned"],
            checks=[
                {
                    "criterion_id": "A recorded payment id is returned",
                    "passes": True,
                    "contradicts": True,
                    "executable": True,
                }
            ],
            review_count=1,
        )
        self.assertFalse(result["ok"])
        self.assertIn("contradicts-criterion", result["reasons"])

    def test_typo_still_needs_one_review(self):
        result = sdlc_flows.review_floor(
            review_count=0, unit_tests_green=True, change="typo"
        )
        self.assertFalse(result["ok"])
        self.assertFalse(result["waived"])
        self.assertIn("missing-intent-match-review", result["reasons"])

    def test_green_tests_do_not_waive_review(self):
        result = sdlc_flows.review_floor(
            review_count=0, unit_tests_green=True, change="story"
        )
        self.assertFalse(result["ok"])
        self.assertIn("missing-intent-match-review", result["reasons"])

    def test_high_stakes_needs_two_reviews(self):
        one = sdlc_flows.review_floor(
            review_count=1,
            unit_tests_green=True,
            change="public-contract",
            high_stakes=True,
        )
        two = sdlc_flows.review_floor(
            review_count=2,
            unit_tests_green=False,
            change="outbound",
            high_stakes=True,
        )
        self.assertFalse(one["ok"])
        self.assertIn("missing-second-review", one["reasons"])
        self.assertTrue(two["ok"])

    def test_unmapped_test_plan_fails(self):
        result = sdlc_flows.test_plan_gate(
            {"mapped": [], "reviewed": True, "executable": True},
            ["Balance shows a currency amount"],
        )
        self.assertFalse(result["ok"])
        self.assertIn("unmapped-criteria", result["reasons"])

    def test_unreviewed_plan_fails_even_when_mapped(self):
        result = sdlc_flows.test_plan_gate(
            {
                "mapped": ["Balance shows a currency amount"],
                "reviewed": False,
                "executable": True,
            },
            ["Balance shows a currency amount"],
        )
        self.assertFalse(result["ok"])
        self.assertIn("missing-plan-review", result["reasons"])

    def test_role_gates_are_named(self):
        for role in ("product-owner", "scrum-master", "tester"):
            gates = sdlc_flows.role_gates(role)
            self.assertIn("intent-match-review", gates)

    def test_story_flow_stops_before_ready_without_criteria(self):
        result = sdlc_flows.story_flow(
            {"intent": "see the balance", "criteria": [], "problems": ["balance"]},
            checks=[],
            review_count=1,
        )
        self.assertEqual(result["stage"], "ready")
        self.assertFalse(result["ready"])

    def test_ready_story_without_checks_fails_intent(self):
        result = sdlc_flows.story_flow(READY_STORY, checks=[], review_count=1)
        self.assertEqual(result["stage"], "intent-match")
        self.assertFalse(result["ok"])
        self.assertIn("missing-executable-check", result["reasons"])

    def test_documented_cap_rejects_a_larger_brief(self):
        over = capability_profile.brief_fits(FIXTURE_CAP, "fixture-host", 32769)
        exact = capability_profile.brief_fits(FIXTURE_CAP, "fixture-host", 32768)
        self.assertFalse(over["fits"])
        self.assertEqual(over["cap"], 32768)
        self.assertTrue(exact["fits"])

    def test_missing_or_unknown_profile_uses_triage_defaults(self):
        missing = capability_profile.brief_fits(FIXTURE_CAP, "no-such-host", 10**9)
        unknown = capability_profile.brief_fits(FIXTURE_CAP, "open-host", 10**9)
        self.assertTrue(missing["fits"])
        self.assertEqual(missing["mode"], "triage-defaults")
        self.assertTrue(unknown["fits"])
        self.assertEqual(unknown["mode"], "triage-defaults")

    def test_shipped_profile_numbers_are_cited_or_unknown(self):
        text = (ROOT / "references" / "profiles" / "capabilities.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual([], capability_profile.unsourced_numbers(text))
        for host in (
            "claude",
            "codex",
            "grok",
            "gemini",
            "copilot",
            "opencode",
            "cursor",
            "grok-bot",
        ):
            row = capability_profile.brief_fits(text, host, 10**9)
            self.assertTrue(row["fits"])
            self.assertEqual(row["mode"], "triage-defaults")


if __name__ == "__main__":
    unittest.main()
