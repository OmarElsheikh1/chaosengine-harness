"""On-demand cited host caps. Unknown and missing hosts keep triage defaults."""

from __future__ import annotations


def _blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            current.append(line.strip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _tables(text: str) -> list[list[dict[str, str]]]:
    tables: list[list[dict[str, str]]] = []
    for block in _blocks(text):
        header = _cells(block[0])
        rows: list[dict[str, str]] = []
        for line in block[1:]:
            cells = _cells(line)
            if cells and all(set(cell) <= set("-: ") and cell for cell in cells):
                continue
            rows.append(dict(zip(header, cells)))
        tables.append(rows)
    return tables


def _source(row: dict[str, str]) -> str:
    for key, value in row.items():
        if key.casefold() == "source":
            return value.strip()
    return ""


def _cited(source: str) -> bool:
    if not source or source.casefold() == "unknown":
        return False
    return "http://" in source or "https://" in source or "/" in source or "." in source


def unsourced_numbers(text: str) -> list[str]:
    """Numeric cells with no source pin. `unknown` is not a number."""
    bad: list[str] = []
    for rows in _tables(text):
        for row in rows:
            source = _source(row)
            for key, value in row.items():
                if key.casefold() == "source":
                    continue
                if any(character.isdigit() for character in value) and not _cited(source):
                    bad.append(f"{key}={value}")
    return bad


def _cap_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for table in _tables(text):
        for row in table:
            keys = {key.casefold() for key in row}
            if "id" in keys and "hard_cap_bytes" in keys:
                rows.append({key.casefold(): value for key, value in row.items()})
    return rows


def brief_fits(text: str, host: str, brief_bytes: int) -> dict:
    """Reject a brief over a cited hard cap. Unknown caps do not invent one."""
    matched = next((row for row in _cap_rows(text) if row.get("id") == host), None)
    if matched is None:
        return {"fits": True, "mode": "triage-defaults", "cap": None}
    raw = matched.get("hard_cap_bytes", "unknown").strip()
    if not raw or raw.casefold() == "unknown":
        return {"fits": True, "mode": "triage-defaults", "cap": None}
    cap = int(raw)
    return {"fits": brief_bytes <= cap, "mode": "published-cap", "cap": cap}
