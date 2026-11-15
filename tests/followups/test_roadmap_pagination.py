"""#14: paginate epic sub-issues, and keep ROADMAP.md equal to render()."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "roadmap-epic.json"


def _load():
    spec = importlib.util.spec_from_file_location("roadmap_followups", ROOT / ".github" / "scripts" / "roadmap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _page(numbers: list[int], *, has_next: bool, cursor: str | None) -> dict:
    return {
        "data": {
            "repository": {
                "issue": {
                    "number": 8056,
                    "title": "Epic",
                    "url": "https://github.com/ShaftHQ/SHAFT_ENGINE/issues/8056",
                    "state": "OPEN",
                    "subIssues": {
                        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                        "nodes": [
                            {
                                "number": number,
                                "title": f"Issue {number}",
                                "url": f"https://github.com/ShaftHQ/SHAFT_ENGINE/issues/{number}",
                                "state": "OPEN",
                                "repository": {"nameWithOwner": "ShaftHQ/SHAFT_ENGINE"},
                            }
                            for number in numbers
                        ],
                    },
                }
            }
        }
    }


def test_epic_target_is_the_transferred_harness_issue():
    roadmap = _load()
    assert (roadmap.EPIC_OWNER, roadmap.EPIC_REPO, roadmap.EPIC_NUMBER) == (
        "ShaftHQ",
        "chaosengine-harness",
        41,
    )


def test_pagination_requests_the_next_page_when_the_first_is_full(monkeypatch):
    roadmap = _load()
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        cursor = next((item.split("=", 1)[1] for item in cmd if str(item).startswith("cursor=")), "")
        body = _page([1], has_next=True, cursor="CUR2") if not cursor else _page([2], has_next=False, cursor=None)

        class Result:
            stdout = json.dumps(body)

        return Result()

    monkeypatch.setattr(roadmap.subprocess, "run", fake_run)
    epic = roadmap.fetch()
    assert len(calls) == 2
    assert any(item == "cursor=CUR2" for item in calls[1])
    assert [node["number"] for node in epic["subIssues"]["nodes"]] == [1, 2]


def test_roadmap_md_matches_render():
    roadmap = _load()
    epic = json.loads(FIXTURE.read_text(encoding="utf-8"))
    live = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    rendered = roadmap.render(epic, "2026-11-15")
    assert roadmap._body(live) == roadmap._body(rendered)
