"""Word-timing gate: missing evidence fails closed; a complete file passes."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "design_qc_wordtiming", ROOT / "addons/design-skills/scripts/design_qc.py"
)
design_qc = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = design_qc
assert _SPEC.loader is not None
_SPEC.loader.exec_module(design_qc)

VALID = {
    "lines": [
        {
            "text": "Fluent waits.",
            "words": [
                {"text": "Fluent", "start": 0.0, "end": 0.42},
                {"text": "waits", "start": 0.42, "end": 0.9},
            ],
            "picture": "queue holds one job",
        },
        {
            "text": "Sleep guesses.",
            "words": [{"text": "Sleep", "start": 1.0, "end": 1.4}],
            "picture": "clock drifts off the cue",
        },
    ]
}


def _run(capsys, path: Path) -> tuple[int, str]:
    code = design_qc.main(["wordtiming", str(path)])
    return code, capsys.readouterr().out


def test_missing_evidence_fails(tmp_path: Path, capsys) -> None:
    cases = [
        ("", "empty-file"),
        ("{}", "missing-lines"),
        (json.dumps({"lines": []}), "missing-lines"),
        (
            json.dumps(
                {
                    "lines": [
                        {
                            "text": "Fluent waits.",
                            "words": [],
                            "picture": "queue holds",
                        }
                    ]
                }
            ),
            "no-words",
        ),
        (
            json.dumps(
                {
                    "lines": [
                        {
                            "text": "Fluent waits.",
                            "words": [{"text": "Fluent", "start": 0.0, "end": 0.4}],
                            "picture": "",
                        }
                    ]
                }
            ),
            "no-picture",
        ),
        (
            json.dumps(
                {
                    "lines": [
                        {
                            "text": "  ",
                            "words": [{"text": "Fluent", "start": 0.0, "end": 0.4}],
                            "picture": "queue holds",
                        }
                    ]
                }
            ),
            "empty-text",
        ),
        (
            json.dumps(
                {
                    "lines": [
                        {
                            "text": "Fluent waits.",
                            "words": [{"text": "Fluent", "start": 0.4, "end": 0.4}],
                            "picture": "queue holds",
                        }
                    ]
                }
            ),
            "end-not-after-start",
        ),
    ]
    for raw, reason in cases:
        path = tmp_path / "timings.json"
        path.write_text(raw, encoding="utf-8")
        code, out = _run(capsys, path)
        assert code != 0, reason
        assert reason in out


def test_valid_word_timing_passes(tmp_path: Path, capsys) -> None:
    path = tmp_path / "timings.json"
    path.write_text(json.dumps(VALID), encoding="utf-8")
    code, out = _run(capsys, path)
    assert code == 0
    assert '"status": "pass"' in out
