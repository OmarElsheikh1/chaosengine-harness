"""Non-coding SDLC gates for product owners, scrum masters, and testers.

Mechanical checks only. Whether a split is wise, or whether intent is truly
met, stays in the adversarial review.
"""

from __future__ import annotations

UNTESTABLE_CRITERIA = frozenset({"make it nice"})

ROLE_GATES = {
    "product-owner": (
        "acceptance-criteria",
        "single-problem",
        "intent-match-review",
    ),
    "scrum-master": (
        "acceptance-criteria",
        "single-problem",
        "ready-gate",
        "intent-match-review",
    ),
    "tester": (
        "criteria-mapping",
        "executable-checks",
        "plan-review",
        "intent-match-review",
    ),
}


def role_gates(role: str) -> tuple[str, ...]:
    try:
        return ROLE_GATES[role]
    except KeyError as error:
        raise ValueError(f"unknown role: {role}") from error


def _text(criterion: object) -> str:
    if isinstance(criterion, dict):
        return str(criterion.get("text") or "").strip()
    return str(criterion).strip()


def _criterion_id(criterion: object) -> str:
    if isinstance(criterion, dict) and criterion.get("id"):
        return str(criterion["id"])
    return _text(criterion)


def _testable(criterion: object) -> bool:
    if isinstance(criterion, dict) and criterion.get("testable") is False:
        return False
    text = _text(criterion)
    return bool(text) and text.casefold() not in UNTESTABLE_CRITERIA


def _dedupe(reasons: list[str]) -> list[str]:
    return list(dict.fromkeys(reasons))


def ready_gate(story: dict) -> dict:
    """Fail closed when criteria are missing, untestable, or hide two problems."""
    reasons: list[str] = []
    problems = list(story.get("problems") or [])
    if len(problems) > 1:
        reasons.append("mixed-problems")
    elif len(problems) != 1:
        reasons.append("missing-problem")
    criteria = list(story.get("criteria") or [])
    if not criteria:
        reasons.append("missing-criteria")
    elif any(not _testable(item) for item in criteria):
        reasons.append("untestable-criteria")
    return {"ready": not reasons, "reasons": _dedupe(reasons)}


def refine(item: dict) -> dict:
    """Backlog refinement exits through the ready gate."""
    return ready_gate(item)


def intent_match(
    *,
    criteria,
    checks,
    review_count: int,
    high_stakes: bool = False,
) -> dict:
    """Passing checks do not excuse a contradiction or a skipped review."""
    reasons: list[str] = []
    if review_count < 1:
        reasons.append("missing-intent-match-review")
    if high_stakes and review_count < 2:
        reasons.append("missing-second-review")
    ids = {_criterion_id(item) for item in criteria}
    if not checks:
        reasons.append("missing-executable-check")
    for check in checks:
        if check.get("contradicts"):
            reasons.append("contradicts-criterion")
        if check.get("criterion_id") not in ids:
            reasons.append("unmapped-check")
        if check.get("executable") is False:
            reasons.append("missing-executable-check")
    reasons = _dedupe(reasons)
    return {"ok": not reasons, "reasons": reasons}


def review_floor(
    *,
    review_count: int,
    unit_tests_green: bool,
    change: str = "change",
    high_stakes: bool = False,
) -> dict:
    """One adversarial review, two when high-stakes. A green job cannot waive it."""
    reasons: list[str] = []
    if review_count < 1:
        reasons.append("missing-intent-match-review")
    if high_stakes and review_count < 2:
        reasons.append("missing-second-review")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "waived": False,
        "change": change,
        "unit_tests_green": bool(unit_tests_green),
    }


def test_plan_gate(plan: dict, criteria) -> dict:
    """Every acceptance criterion must be mapped, and the plan must be reviewed."""
    reasons: list[str] = []
    mapped = set(plan.get("mapped") or [])
    if any(_criterion_id(item) not in mapped for item in criteria):
        reasons.append("unmapped-criteria")
    if not plan.get("reviewed"):
        reasons.append("missing-plan-review")
    if plan.get("executable") is False:
        reasons.append("missing-executable-check")
    return {"ok": not reasons, "reasons": reasons}


def story_flow(story: dict, checks, *, review_count: int, high_stakes: bool = False) -> dict:
    """Story, then criteria, then executable checks, then intent-match."""
    ready = ready_gate(story)
    if not ready["ready"]:
        return {"stage": "ready", "ok": False, **ready}
    intent = intent_match(
        criteria=list(story.get("criteria") or []),
        checks=checks,
        review_count=review_count,
        high_stakes=high_stakes,
    )
    return {"stage": "intent-match", "ready": True, **intent}
