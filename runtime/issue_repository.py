"""Choose the GitHub repository for one upstream defect.

A ChaosEngine harness defect is filed on ShaftHQ/chaosengine-harness.
A SHAFT_ENGINE product defect is filed on ShaftHQ/SHAFT_ENGINE.
Naming the other repository as the destination does not move the defect.
"""

from __future__ import annotations

import re

HARNESS_REPO = "ShaftHQ/chaosengine-harness"
SHAFT_REPO = "ShaftHQ/SHAFT_ENGINE"

_DESTINATION = re.compile(
    r"\bon\s+(?:the\s+)?(?:shaft engine|chaosengine harness|chaos engine)\b"
)
_HARNESS = ("chaosengine harness", "chaos engine", "chaosengine")
_SHAFT = ("shaft engine",)


def choose_issue_repository(subject: str) -> str:
    """Return the one repo that owns this defect.

    A destination clause (``on shaft engine`` / ``on chaosengine harness``)
    is not the defect. Raises ValueError when the remaining subject names
    both products or neither. One issue owns one product.
    """
    text = " ".join(subject.casefold().replace("_", " ").replace("-", " ").split())
    text = _DESTINATION.sub(" ", text)
    text = " ".join(text.split())
    harness = any(marker in text for marker in _HARNESS)
    shaft = any(marker in text for marker in _SHAFT)
    if harness and shaft:
        raise ValueError(
            "one issue owns one product; split the harness defect from the SHAFT_ENGINE defect"
        )
    if harness:
        return HARNESS_REPO
    if shaft:
        return SHAFT_REPO
    raise ValueError(
        "name whether the defect is in the chaosengine harness or in SHAFT_ENGINE"
    )
