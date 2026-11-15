"""Shipped sentences for #8032 R4–R5 and #8048 R3, R4, and R6."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_UNVERIFIED = (
    "Do not write unverified model output into trusted memory, heuristics, or skills."
)
_LESSON = "A lesson that cannot name an outcome does not become a skill."
_SUBTRACT = (
    "Name what was deleted or reused before any new file, skill, or abstraction."
)
_DRAFT = "If an agent drafted the text, say so in the message."
_UNCHECKED = "do not send the unchecked ones"
_READ_ONLY = "runs none of the source's code, installers, or hooks"
_FIRST_LOOK = "previous pin: none (first look)"


class EpicDocAcceptanceTest(unittest.TestCase):
    def test_memory_and_self_improve_refuse_unverified_writes(self):
        memory = (ROOT / "references/memory-provenance.md").read_text(encoding="utf-8")
        skill = (ROOT / "skills/self-improve/SKILL.md").read_text(encoding="utf-8")
        self.assertIn(_UNVERIFIED, memory)
        self.assertIn(_UNVERIFIED, skill)
        self.assertIn(_LESSON, skill)

    def test_pre_done_names_subtract_before_add(self):
        text = (ROOT / "skills/pre-done-self-review/SKILL.md").read_text(encoding="utf-8")
        self.assertIn(_SUBTRACT, text)

    def test_outbound_gate_discloses_agent_drafts(self):
        text = (ROOT / "references/outbound-send.md").read_text(encoding="utf-8")
        self.assertIn(_DRAFT, text)
        self.assertIn(_UNCHECKED, text)

    def test_security_names_the_former_harness_tree(self):
        text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("chaos-engine/", text)
        self.assertIn("In scope:", text)
        self.assertIn("Out of scope:", text)

    def test_external_study_reads_files_and_records_a_first_look(self):
        text = (ROOT / "skills/learn-from-external-harnesses/SKILL.md").read_text(encoding="utf-8")
        self.assertIn(_READ_ONLY, text)
        self.assertIn(_FIRST_LOOK, text)
        self.assertLess(len(text.splitlines()), 150)


if __name__ == "__main__":
    unittest.main()
