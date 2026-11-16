#!/usr/bin/env python3
"""Scratch notes for one session and every subagent it starts.

SessionStart creates the folder once. The root session and its subagents append
notes there. SessionEnd, and only SessionEnd, reads those notes once when the
session has lasted more than one hour, files enhancement notes as GitHub
issues, and writes one report.
"""

from __future__ import annotations

import json
import os
import re
import subprocess  # nosec B404 - fixed gh argv for the session-end filing.
import time
from datetime import UTC, datetime
from pathlib import Path

KINDS = frozenset({"thinking", "repetition", "issue", "enhancement", "highlight"})
ONE_HOUR_SECONDS = 3600
FILE_BUDGET_SECONDS = 2.0
MAX_FILED = 8
MAX_TEXT = 400
MAX_NOTES = 200
_SECRET = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:password|secret|api[_-]?key|access[_-]?token|token|credential)\s*[:=]\s*\S+)"
)
_PATH = re.compile(r"(?:[A-Za-z]:\\|/(?:home|Users|tmp|var|private|media)/)[^\s\"']+")
_ISSUE_URL = re.compile(r"https://github\.com/\S+/issues/[1-9][0-9]*")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_KIND_LINE = re.compile(
    r"(?i)^(thinking|repetition|issue|enhancement|highlight)\s*:\s*(.+)$"
)


def folder_key(session_id: str) -> str:
    import hashlib

    return hashlib.sha256(session_id.strip().encode("utf-8")).hexdigest()[:32]


def relative_folder(session_id: str) -> str:
    return f".chaos-engine-state/session-scratch/{folder_key(session_id)}"


def folder(project: Path, session_id: str) -> Path:
    return Path(project) / relative_folder(session_id)


def scrub(value: object) -> str:
    text = " ".join(str(value or "").split())
    text = _SECRET.sub("[redacted]", text)
    text = _PATH.sub("[path]", text)
    return text[:MAX_TEXT].strip()


def _howto(session_id: str) -> str:
    relative = relative_folder(session_id)
    return (
        "# Session scratch\n\n"
        f"Append one JSON object per line to `{relative}/notes.jsonl`.\n\n"
        "Kinds: thinking, repetition, issue, enhancement, highlight.\n"
        'Example: {"kind":"enhancement","text":"what should change"}\n\n'
        "The root session and every subagent share this folder. "
        "Write the thinking, the repetition, the issue, the enhancement, "
        "or the highlight when it happens. No secrets and no private paths.\n"
        "The retrospective reads this folder once, at session end, and only "
        "when the session exceeded one hour.\n"
    )


def _rule(session_id: str) -> str:
    return _howto(session_id)


def ensure(project: Path, session_id: str) -> bool:
    """Create the shared folder once. Return True only on the creating call."""
    if not str(session_id or "").strip():
        return False
    target = folder(project, session_id)
    target.mkdir(parents=True, exist_ok=True)
    created = False
    marker = target / "session.json"
    payload = json.dumps({"createdAt": datetime.now(UTC).isoformat()}).encode("utf-8")
    try:
        descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        created = False
    else:
        try:
            os.write(descriptor, payload)
        finally:
            os.close(descriptor)
        created = True
    howto = target / "HOWTO.md"
    if not howto.is_file():
        howto.write_text(_howto(session_id), encoding="utf-8")
    _publish_rule(project, session_id)
    return created


def _publish_rule(project: Path, session_id: str) -> None:
    """Grok reads `.grok/rules`, including inside subagents. SessionStart stdout does not."""
    rules = Path(project) / ".grok" / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / "session-scratch.md").write_text(_rule(session_id), encoding="utf-8")


def append_note(project: Path, session_id: str, *, agent: str, kind: str, text: object) -> bool:
    cleaned = scrub(text)
    label = kind.strip().casefold()
    if not cleaned or label not in KINDS or not str(session_id or "").strip():
        return False
    target = folder(project, session_id)
    target.mkdir(parents=True, exist_ok=True)
    row = {
        "at": datetime.now(UTC).isoformat(),
        "agent": scrub(agent) or "root",
        "kind": label,
        "text": cleaned,
    }
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    descriptor = os.open(target / "notes.jsonl", os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
    try:
        os.write(descriptor, line.encode("utf-8"))
    finally:
        os.close(descriptor)
    return True


def _agents_path(project: Path, session_id: str) -> Path:
    return folder(project, session_id) / "agents.json"


def _with_agents(project: Path, session_id: str, change) -> None:
    target = folder(project, session_id)
    target.mkdir(parents=True, exist_ok=True)
    lock = target / ".lock"
    acquired = False
    for _ in range(30):
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            time.sleep(0.01)
            continue
        os.close(descriptor)
        acquired = True
        break
    if not acquired:
        return
    try:
        path = _agents_path(project, session_id)
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            current = {"open": []}
        open_ids = [str(item) for item in current.get("open", []) if str(item)]
        path.write_text(
            json.dumps({"open": change(open_ids)}, separators=(",", ":")),
            encoding="utf-8",
        )
    finally:
        lock.unlink(missing_ok=True)


def open_agent(project: Path, session_id: str, agent: str) -> None:
    name = scrub(agent)
    if not name:
        return

    def change(open_ids: list[str]) -> list[str]:
        if name not in open_ids:
            open_ids.append(name)
        return open_ids

    _with_agents(project, session_id, change)


def close_agent(project: Path, session_id: str, agent: str) -> None:
    name = scrub(agent)
    if not name:
        return

    def change(open_ids: list[str]) -> list[str]:
        return [item for item in open_ids if item != name]

    _with_agents(project, session_id, change)


def open_agents(project: Path, session_id: str) -> list[str]:
    try:
        payload = json.loads(_agents_path(project, session_id).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    return [str(item) for item in payload.get("open", []) if str(item)]


def capture_message(project: Path, session_id: str, agent: str, event: dict) -> None:
    chunks: list[str] = []
    for key in ("thinking", "reasoning", "last_assistant_message", "lastAssistantMessage"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            chunks.append(value.strip())
    if not chunks:
        return
    combined = "\n".join(chunks)
    append_note(project, session_id, agent=agent, kind="thinking", text=combined)
    for line in combined.splitlines():
        match = _KIND_LINE.match(line.strip())
        if match is None:
            continue
        append_note(
            project,
            session_id,
            agent=agent,
            kind=match.group(1).lower(),
            text=match.group(2),
        )


def load_notes(project: Path, session_id: str) -> list[dict]:
    path = folder(project, session_id) / "notes.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return []
    notes: list[dict] = []
    for line in lines[-MAX_NOTES:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "").casefold()
        text = scrub(row.get("text"))
        if kind not in KINDS or not text:
            continue
        notes.append({"kind": kind, "text": text, "agent": scrub(row.get("agent")) or "unknown"})
    return notes


def upstream_repo(project: Path) -> str:
    chosen = os.environ.get("CHAOS_ENGINE_UPSTREAM_REPO", "").strip()
    if _REPO.fullmatch(chosen):
        return chosen
    path = Path(project) / "scripts" / "ci" / "chaos-engine-upstream.txt"
    try:
        line = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except (OSError, UnicodeError, IndexError):
        return ""
    return line if _REPO.fullmatch(line) else ""


def _default_run(deadline: float):
    def run(args: list[str]) -> tuple[int, str]:
        remaining = deadline - time.monotonic()
        if remaining <= 0.05:
            return 124, ""
        try:
            proc = subprocess.run(  # nosec B603 - gh argv is built in this module.
                args,
                capture_output=True,
                text=True,
                timeout=remaining,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return 124, ""
        return proc.returncode, (proc.stdout or "") + "\n" + (proc.stderr or "")

    return run


def _titles(stdout: str) -> set[str]:
    start = stdout.find("[")
    end = stdout.rfind("]")
    if start < 0 or end < start:
        return set()
    try:
        rows = json.loads(stdout[start : end + 1])
    except json.JSONDecodeError:
        return set()
    if not isinstance(rows, list):
        return set()
    return {str(row.get("title") or "") for row in rows if isinstance(row, dict)}


def _issue_title(text: str, used: set[str]) -> str:
    """Keep two different notes that share a 72-character prefix as two issues."""
    import hashlib

    base = "Session enhancement: " + text[:72]
    if base.casefold() not in used:
        return base
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    room = max(0, 72 - len(digest) - 1)
    return "Session enhancement: " + text[:room] + " " + digest


def file_enhancements(
    project: Path,
    session_id: str,
    notes: list[dict],
    run,
) -> tuple[list[str], list[str]]:
    """File each distinct enhancement once. Return filed URLs and texts left unfiled."""
    repo = upstream_repo(project)
    filed: list[str] = []
    skipped: list[str] = []
    seen: set[str] = set()
    titles: set[str] = set()
    target = folder(project, session_id)
    for note in notes:
        if note.get("kind") != "enhancement":
            continue
        text = str(note.get("text") or "")
        identity = text.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        title = _issue_title(text, titles)
        titles.add(title.casefold())
        if len(filed) >= MAX_FILED:
            skipped.append(text)
            continue
        list_args = ["gh", "issue", "list", "--state", "open", "--limit", "20", "--search", title, "--json", "title"]
        if repo:
            list_args[3:3] = ["--repo", repo]
        code, stdout = run(list_args)
        if code != 0:
            skipped.append(text)
            continue
        if title in _titles(stdout):
            continue
        body = target / "pending-issue.txt"
        body.write_text(text + "\n\nFiled by the session retrospective.\n", encoding="utf-8")
        create_args = ["gh", "issue", "create", "--title", title, "--body-file", str(body)]
        if repo:
            create_args[3:3] = ["--repo", repo]
        code, stdout = run(create_args)
        match = _ISSUE_URL.search(stdout)
        if code == 0 and match is not None:
            filed.append(match.group(0).rstrip(").,"))
        else:
            skipped.append(text)
    return filed, skipped


def render_report(
    notes: list[dict],
    *,
    elapsed: float,
    filed: list[str],
    skipped: list[str],
    still_open: list[str],
) -> str:
    sections = ["thinking", "repetition", "issue", "enhancement", "highlight"]
    lines = [
        "# Session retrospective",
        "",
        "The session exceeded one hour. This report was written once at session end.",
        "",
        f"Elapsed seconds: {int(elapsed)}.",
        "",
    ]
    if still_open:
        lines.append("Subagents still open at session end: " + ", ".join(still_open) + ".")
        lines.append("")
    for kind in sections:
        lines.append(f"## {kind.capitalize()}")
        rows = [note["text"] for note in notes if note["kind"] == kind]
        if rows:
            lines.extend(f"- {text}" for text in rows)
        else:
            lines.append("- none")
        lines.append("")
    lines.append("## Filed")
    if filed:
        lines.extend(f"- {url}" for url in filed)
    elif any(note["kind"] == "enhancement" for note in notes):
        lines.append("- not filed")
    else:
        lines.append("- nothing actionable")
    if skipped:
        lines.append("")
        lines.append("Not filed in this pass:")
        lines.extend(f"- {text}" for text in skipped)
    lines.append("")
    return "\n".join(lines)


def retrospective(project: Path, session_id: str, elapsed: float | None, *, run=None) -> str | None:
    """Ingest the folder once. Return the report, or None when this end is not the one."""
    if not str(session_id or "").strip():
        return None
    if elapsed is None or elapsed <= ONE_HOUR_SECONDS:
        return None
    target = folder(project, session_id)
    if not target.is_dir():
        target.mkdir(parents=True, exist_ok=True)
    done = target / "retro.done"
    try:
        descriptor = os.open(done, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return None
    os.close(descriptor)
    notes = load_notes(project, session_id)
    runner = run or _default_run(time.monotonic() + FILE_BUDGET_SECONDS)
    try:
        filed, skipped = file_enhancements(project, session_id, notes, runner)
    except Exception:
        filed, skipped = [], [note["text"] for note in notes if note["kind"] == "enhancement"]
    report = render_report(
        notes,
        elapsed=elapsed,
        filed=filed,
        skipped=skipped,
        still_open=open_agents(project, session_id),
    )
    (target / "report.md").write_text(report, encoding="utf-8")
    with done.open("a", encoding="utf-8") as handle:
        handle.write(datetime.now(UTC).isoformat() + "\n")
    return report
