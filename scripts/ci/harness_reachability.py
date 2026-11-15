#!/usr/bin/env python3
"""Markdown link walk shared by the architect and technical-presentations parity tests.

The walk follows markdown links and records a broken target instead of
skipping it. Prose mentions are not links.
"""
from __future__ import annotations

import re
from pathlib import Path

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]*\]\(([^)]+)\)")
URI_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def _record_overlay_pointer(
    root: Path,
    path: Path,
    current: str,
    raw: str,
    target: str,
    reached: set[str],
    broken: list[str],
    queue: list[str],
) -> bool:
    """Record a `.chaos-engine/` link by its spelling before symlink resolution."""
    lexical = path.parent / target
    try:
        relative = lexical.relative_to(root).as_posix()
    except ValueError:
        return False
    if relative != ".chaos-engine" and not relative.startswith(".chaos-engine/"):
        return False
    if ".." in Path(relative).parts:
        return False
    twin = root / relative.removeprefix(".chaos-engine/")
    if lexical.exists() or twin.exists():
        reached.add(relative)
        if twin.is_file():
            queue.append(twin.relative_to(root).as_posix())
        return True
    broken.append(f"{current} -> {raw}")
    return True


def link_walk(root: Path, entrypoint: str) -> tuple[set[str], list[str]]:
    """Walk markdown links from the entrypoint. Return reached paths and broken links."""
    root = root.resolve()
    reached: set[str] = set()
    broken: list[str] = []
    queue = [entrypoint]
    while queue:
        current = queue.pop()
        if current in reached:
            continue
        reached.add(current)
        path = root / current
        if path.suffix != ".md" or not path.is_file():
            continue
        if "templates" in Path(current).parts:
            continue
        for raw in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
            target = raw.strip().strip("<>").split("#", 1)[0]
            if not target or URI_SCHEME.match(target):
                continue
            if _record_overlay_pointer(root, path, current, raw, target, reached, broken, queue):
                continue
            resolved = (path.parent / target).resolve()
            try:
                relative = resolved.relative_to(root).as_posix()
            except ValueError:
                broken.append(f"{current} -> {raw} (escapes the repository)")
                continue
            if relative == ".chaos-engine" or relative.startswith(".chaos-engine/"):
                twin = root / relative.removeprefix(".chaos-engine/")
                if resolved.exists() or twin.exists():
                    reached.add(relative)
                    if twin.is_file():
                        queue.append(twin.relative_to(root).as_posix())
                    continue
                broken.append(f"{current} -> {raw}")
                continue
            if not resolved.exists():
                broken.append(f"{current} -> {raw}")
                continue
            queue.append(relative)
    return reached, broken
