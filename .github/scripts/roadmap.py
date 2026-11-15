#!/usr/bin/env python3
"""Generate ROADMAP.md from the ChaosEngine epic and its sub-issues.

The roadmap is a view of the epic, not a second tracker. Sub-issue order is
the epic's suggested order. Run from the repository root:

    python3 .github/scripts/roadmap.py            # rewrite ROADMAP.md
    python3 .github/scripts/roadmap.py --check    # exit 1 if ROADMAP.md is stale

Needs the GitHub CLI (`gh`) signed in, or `--from-json FILE` for offline use.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess  # nosec B404 - runs the fixed `gh api graphql` command only.
import sys
from pathlib import Path

# SHAFT_ENGINE#8056 was transferred here. GraphQL does not follow that redirect.
EPIC_OWNER = "ShaftHQ"
EPIC_REPO = "chaosengine-harness"
EPIC_NUMBER = 41
ROADMAP = Path("ROADMAP.md")
GENERATED_PREFIX = "Generated on "

QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      number title url state
      subIssues(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { number title url state repository { nameWithOwner } }
      }
    }
  }
}
"""


def _graphql_page(owner: str, repo: str, number: int, cursor: str | None) -> dict:
    """One sub-issue page. ``cursor`` None is the first page."""
    cmd = [
        "gh", "api", "graphql", "-f", f"query={QUERY}",
        "-f", f"owner={owner}", "-f", f"repo={repo}", "-F", f"number={number}",
    ]
    if cursor:
        cmd.extend(["-f", f"cursor={cursor}"])
    try:
        out = subprocess.run(  # nosec B603 B607 - fixed argv, no shell.
            cmd, check=True, capture_output=True, text=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        raise SystemExit(f"GitHub API error: {detail or error.returncode}") from error
    payload = json.loads(out)
    if payload.get("errors"):
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    issue = ((payload.get("data") or {}).get("repository") or {}).get("issue")
    if issue is None:
        raise SystemExit(f"epic {owner}/{repo}#{number} not found")
    return issue


def fetch(owner: str = EPIC_OWNER, repo: str = EPIC_REPO, number: int = EPIC_NUMBER) -> dict:
    """Return the epic and every sub-issue page, via `gh api graphql`."""
    cursor: str | None = None
    seen: set[str] = set()
    nodes: list = []
    epic: dict | None = None
    while True:
        page = _graphql_page(owner, repo, number, cursor)
        if epic is None:
            epic = {key: page[key] for key in ("number", "title", "url", "state") if key in page}
        nodes.extend((page.get("subIssues") or {}).get("nodes") or [])
        info = (page.get("subIssues") or {}).get("pageInfo") or {}
        if not info.get("hasNextPage"):
            break
        cursor = str(info.get("endCursor") or "")
        if not cursor or cursor in seen:
            raise SystemExit("epic sub-issues page is missing a new endCursor")
        seen.add(cursor)
    assert epic is not None
    epic["subIssues"] = {"pageInfo": {"hasNextPage": False}, "nodes": nodes}
    return epic


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render(epic: dict, today: str) -> str:
    """Render the roadmap Markdown. `today` is an ISO date string."""
    nodes = (epic.get("subIssues") or {}).get("nodes") or []
    open_items = [n for n in nodes if n["state"] == "OPEN"]
    closed_items = [n for n in nodes if n["state"] != "OPEN"]
    lines = [
        "# Roadmap",
        "",
        f"This page is generated from epic [#{epic['number']}]({epic['url']}) ({_cell(epic['title'])}) "
        "and its sub-issues, in the epic's order. Edit the epic, not this file.",
        "",
        f"{GENERATED_PREFIX}{today}. Regenerate with `python3 .github/scripts/roadmap.py`.",
        "",
        "## Open",
        "",
    ]
    if open_items:
        lines += ["| # | Issue | Title |", "| --- | --- | --- |"]
        for i, n in enumerate(open_items, 1):
            lines.append(f"| {i} | [{n['repository']['nameWithOwner']}#{n['number']}]({n['url']}) | {_cell(n['title'])} |")
    else:
        lines.append("None.")
    lines += ["", "## Done", ""]
    if closed_items:
        for n in closed_items:
            lines.append(f"- [{n['repository']['nameWithOwner']}#{n['number']}]({n['url']}) {_cell(n['title'])}")
    else:
        lines.append("None yet.")
    return "\n".join(lines) + "\n"


def _body(text: str) -> str:
    """Drop the generated-date line so `--check` compares content only."""
    return "\n".join(l for l in text.splitlines() if not l.startswith(GENERATED_PREFIX))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if ROADMAP.md differs from the epic")
    parser.add_argument("--from-json", type=Path, help="read the epic from a saved JSON file (offline)")
    parser.add_argument("--output", type=Path, default=ROADMAP)
    args = parser.parse_args(argv)

    epic = json.loads(args.from_json.read_text(encoding="utf-8")) if args.from_json else fetch()
    text = render(epic, _dt.date.today().isoformat())
    current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
    if args.check:
        if _body(current) != _body(text):
            print(f"{args.output} is stale; run python3 .github/scripts/roadmap.py", file=sys.stderr)
            return 1
        print(f"{args.output} matches the epic")
        return 0
    if _body(current) != _body(text):
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(f"{args.output} already matches the epic")
    return 0


if __name__ == "__main__":
    sys.exit(main())
