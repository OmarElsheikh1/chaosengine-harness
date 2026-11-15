#!/usr/bin/env python3
"""Fail when the ChaosEngine plugin CHANGELOG or COMPATIBILITY misses VERSION.

The portable plugin version is the harness ``VERSION`` file. A release that
bumps it must add ``## <version>`` to the plugin CHANGELOG and name that
version in COMPATIBILITY.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CHANGELOG = Path("agent-plugins/chaos-engine/CHANGELOG.md")
COMPATIBILITY = Path("agent-plugins/chaos-engine/COMPATIBILITY.md")


def engine_version(root: Path) -> str:
    """Return the harness VERSION, which is the plugin version."""
    path = root / "VERSION"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def defects(root: Path) -> list[str]:
    """Return human-readable defects; empty when both files cover the version."""
    version = engine_version(root)
    if not version:
        return ["VERSION has no harness version"]
    problems: list[str] = []
    heading = f"## {version}"
    changelog = root / CHANGELOG
    if not changelog.is_file():
        problems.append(f"{CHANGELOG} has no '{heading}' entry for the harness version in VERSION")
    else:
        lines = changelog.read_text(encoding="utf-8").splitlines()
        if not any(line == heading or line.startswith(heading + " ") for line in lines):
            problems.append(f"{CHANGELOG} has no '{heading}' entry for the harness version in VERSION")
    compatibility = root / COMPATIBILITY
    if not compatibility.is_file() or version not in compatibility.read_text(encoding="utf-8"):
        problems.append(f"{COMPATIBILITY} does not name the harness version {version}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    problems = defects(args.root)
    for problem in problems:
        print(f"plugin-changelog: {problem}", file=sys.stderr)
    if not problems:
        print(f"plugin changelog covers chaos-engine {engine_version(args.root)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
