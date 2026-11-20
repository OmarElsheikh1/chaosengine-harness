"""Issue 18 mcp_policy bullets: safe rewrite, parser refusal, no leftover lock."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ce_mcp_policy_rewrite", ROOT / "runtime" / "mcp_policy.py")
mp = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = mp
_spec.loader.exec_module(mp)

GROK_WITH_GITHUB = (
    'model = "fast"\n'
    "\n"
    "[mcp_servers.github]\n"
    'command = "github-mcp"\n'
    "\n"
    "[mcp_servers.other]\n"
    'command = "other"\n'
)


def _home(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "home"
    (home / ".grok").mkdir(parents=True)
    for var in ("GROK_HOME", "CODEX_HOME", "CLAUDE_CONFIG", "GEMINI_HOME", "COPILOT_HOME", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(home))
    return home


def test_successful_grok_rewrite_leaves_no_chaosengine_lock(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    config = home / ".grok" / "config.toml"
    config.write_text(GROK_WITH_GITHUB, encoding="utf-8")
    result = mp.repair_user_github_mcp(home, gh_healthy=True)
    assert result["stripped"] == [{"host": "grok", "path": str(config), "ids": ["github"]}]
    locks = list(config.parent.glob("*.chaosengine.lock"))
    assert locks == []


def test_removed_ids_empty_when_writer_noops(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    config = home / ".grok" / "config.toml"
    config.write_text(GROK_WITH_GITHUB, encoding="utf-8")
    writer = mp._safe_writer()
    module = sys.modules[writer.__module__]

    def noop(path, transform, validate=None, **_kwargs):
        text = Path(path).read_text(encoding="utf-8")
        transform(text)
        return text, text

    monkeypatch.setattr(module, "update_config_file", noop)
    result = mp.repair_user_github_mcp(home, gh_healthy=True)
    assert result["stripped"] == []
    assert "github" in config.read_text(encoding="utf-8")


def test_toml_problem_refuses_when_parser_missing(monkeypatch):
    writer = mp._safe_writer()
    module = sys.modules[writer.__module__]
    monkeypatch.setattr(module, "_toml", None)
    problem = mp._toml_problem_for('model = "fast"\n')
    assert problem
    assert "parser" in problem.casefold()


def test_toml_problem_reports_non_valueerror(monkeypatch):
    writer = mp._safe_writer()
    module = sys.modules[writer.__module__]

    def loads(_text):
        raise RuntimeError("parser-broke")

    monkeypatch.setattr(module._toml, "loads", loads)
    problem = mp._toml_problem_for("a = 1\n")
    assert problem and "parser-broke" in problem


def test_missing_parser_refuses_the_rewrite_and_leaves_no_lock(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    config = home / ".grok" / "config.toml"
    original = GROK_WITH_GITHUB
    config.write_text(original, encoding="utf-8")
    writer = mp._safe_writer()
    module = sys.modules[writer.__module__]
    monkeypatch.setattr(module, "_toml", None)
    with pytest.raises(OSError):
        mp.repair_user_github_mcp(home, gh_healthy=True)
    assert config.read_text(encoding="utf-8") == original
    assert list(config.parent.glob("*.chaosengine.lock")) == []
