#!/usr/bin/env python3
"""Opt-in raise-the-bar plan (ShaftHQ/SHAFT_ENGINE#8064). Not loaded unless asked.

A raise that would replace the asked deliverable stops for a yes and does not
emit the replacement. Missing access is named. A missed measured target is not a pass.
"""

from __future__ import annotations

TRIGGERS = ("raise the bar", "aim higher", "go deeper", "more ambitious")


def consider(request: dict) -> dict:
    """Return a plan, a stop-for-yes result, or ``taken: False`` when not asked."""
    if not isinstance(request, dict):
        return {"taken": False}
    asked = str(request.get("asked") or "")
    asked_raise = any(phrase in asked.casefold() for phrase in TRIGGERS)
    if not request.get("raise_bar") and not asked_raise:
        return {"taken": False}
    if request.get("replaces_deliverable"):
        return {
            "taken": True,
            "stop_for_yes": True,
            "reason": "the raise would replace the asked deliverable",
        }
    if request.get("spend"):
        return {"taken": True, "stop_for_yes": True, "reason": "the raise would spend money"}
    if request.get("irreversible"):
        return {"taken": True, "stop_for_yes": True, "reason": "the raise cannot be undone"}
    if request.get("prompt_only"):
        return {
            "taken": True,
            "stop_for_yes": False,
            "prompt_only": True,
            "prompt": str(request.get("prompt") or asked),
            "work": None,
        }
    missing = request.get("missing_access") or []
    if not isinstance(missing, list):
        missing = []
    skipped = request.get("skipped")
    if not isinstance(skipped, list):
        skipped = ["angles that would add a second deliverable"]
    result: dict = {
        "taken": True,
        "stop_for_yes": False,
        "outcome": request.get("outcome")
        or "Raise the quality of the same deliverable, not the number of deliverables.",
        "used": list(request.get("used") or ["outcome"]),
        "skipped": list(skipped),
        "check": request.get("check") or "a check the author does not grade",
        "pass_line": request.get("pass_line")
        or "the measured result meets the line, or the miss stays a miss",
        "missing_access": missing,
        "extra_deliverables": False,
        "baseline": None,
    }
    if missing:
        result["pass"] = False
        result["named_gap"] = [
            item.get("name") if isinstance(item, dict) else str(item) for item in missing
        ]
        return result
    if "hard_target" not in request or request.get("hard_target") is None:
        result["pass"] = True
        return result
    if "measured" not in request or request.get("measured") is None:
        result["pass"] = False
        result["unmeasured"] = True
        return result
    measured = request["measured"]
    target = request["hard_target"]
    result["measured"] = measured
    result["hard_target"] = target
    try:
        met = float(measured) >= float(target)
    except (TypeError, ValueError):
        result["pass"] = False
        result["unmeasured"] = True
        return result
    result["pass"] = met
    if not met:
        result["honest_miss"] = True
    return result
