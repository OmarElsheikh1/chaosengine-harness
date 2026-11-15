#!/usr/bin/env python3
"""Skill roots the harness lints. Layout is the repository root, not chaos-engine/."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOTS = ("skills", "vendor/*/skills")


def skill_dirs(root: Path = ROOT) -> list[Path]:
    """Every skill directory under the configured roots (globs allowed)."""
    found: list[Path] = []
    for pattern in SKILLS_ROOTS:
        for skills_root in sorted(root.glob(pattern)):
            if skills_root.is_dir():
                found.extend(sorted(path for path in skills_root.iterdir() if path.is_dir()))
    return found
