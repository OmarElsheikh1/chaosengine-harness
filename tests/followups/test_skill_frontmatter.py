"""#25: SKILL.md name must match its directory and the official description rules."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("skill_frontmatter", ROOT / "runtime" / "skill_compress_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_skill(root: Path, directory: str, frontmatter: str) -> Path:
    skill = root / "skills" / directory
    skill.mkdir(parents=True)
    path = skill / "SKILL.md"
    path.write_text(frontmatter, encoding="utf-8")
    (root / "install.py").write_text("# stub\n", encoding="utf-8")
    return path


def test_mismatched_skill_name_fails_the_audit(tmp_path):
    audit = _load()
    path = _write_skill(
        tmp_path,
        "demo",
        "---\nname: other\ndescription: Use when a demo skill is requested.\n---\n\n# Demo\n",
    )
    errors = audit.frontmatter_errors(path)
    assert errors
    assert any("demo" in error for error in errors)


def test_official_name_and_description_pass(tmp_path):
    audit = _load()
    path = _write_skill(
        tmp_path,
        "demo",
        "---\nname: demo\ndescription: Use when a demo skill is requested.\n---\n\n# Demo\n",
    )
    assert audit.frontmatter_errors(path) == []


def test_in_tree_skill_corpus_passes():
    audit = _load()
    failures = audit.lint_skill_frontmatter(ROOT)
    assert failures == []
