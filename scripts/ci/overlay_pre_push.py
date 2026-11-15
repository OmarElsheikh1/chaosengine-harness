#!/usr/bin/env python3
"""Harness pre-push helpers that live in this repo.

``ce_version_bump_failures`` is the VERSION gate. The push hook calls
``overlay_pre_push_failures(project)`` with no changed-path list; an empty
list does not invent a diff, so a push is not blocked until a caller passes
paths. Full SHAFT overlay checks are not in this tree.
"""
from __future__ import annotations

from pathlib import Path

VERSION_FILE = "VERSION"


def ce_version_bump_failures(root: Path, paths: list[str]) -> list[str]:
    """Require VERSION when harness paths change.

    A path list that already contains ``VERSION`` passes. ``.chaos-engine-state/no-version-bump``
    waives the check for a local run. An empty list is not a diff.
    """
    normalized = [item.replace("\\", "/").removeprefix("./") for item in paths if item]
    if not normalized or VERSION_FILE in normalized:
        return []
    if (root / ".chaos-engine-state" / "no-version-bump").is_file():
        return []
    return [
        "ce-version-bump: harness paths changed without VERSION; "
        "bump VERSION or add <!-- chaos-engine:no-version-bump --> / label ce-no-version-bump"
    ]


def overlay_pre_push_failures(root: Path, paths: list[str] | None = None) -> list[str]:
    """Hook entry. No path list means the caller did not supply a diff."""
    return ce_version_bump_failures(root, list(paths or []))
