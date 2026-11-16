"""Owned install-side bullets from issue 18."""

from __future__ import annotations

import importlib.util
import inspect
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_owned_comment_above_a_foreign_header_is_kept():
    glc = _load("ce_glc_issue18", ROOT / "grok_lean_config.py")
    glc._register_ownership()
    interior = [
        "[compat.claude]\n",
        "hooks = false\n",
        "# keep this note\n",
        "[notes]\n",
        "x = 1\n",
    ]
    kept = "".join(glc._foreign_lines(interior, glc.LEAN_START))
    assert "# keep this note" in kept
    assert "[notes]" in kept
    assert "x = 1" in kept


def test_ui_header_with_a_trailing_comment_is_a_header():
    glc = _load("ce_glc_ui_header", ROOT / "grok_lean_config.py")
    original = '[ui] # user theme\ntheme = "dark"\n'
    merged = glc.merge_grok_ui(original)
    assert merged.count("[ui]") == 1
    data = tomllib.loads(merged)
    assert data["ui"]["theme"] == "dark"
    assert data["ui"]["show_thinking_blocks"] is True


def test_existing_skills_table_is_merged_once():
    glc = _load("ce_glc_skills", ROOT / "grok_lean_config.py")
    original = '[skills]\ndisabled = ["other"]\n'
    merged = glc.merge_lean_skills(original)
    assert merged.count("[skills]") == 1
    data = tomllib.loads(merged)
    assert "other" in data["skills"]["disabled"]
    assert "imagine" in data["skills"]["disabled"]
    assert glc.lean_skills_applied(merged)
    again = glc.merge_lean_skills(merged)
    assert tomllib.loads(again)["skills"]["disabled"] == data["skills"]["disabled"]


def test_outside_compat_tables_are_merged_not_deleted():
    glc = _load("ce_glc_compat", ROOT / "grok_lean_config.py")
    original = (
        "[compat.claude]\n"
        "skills = true\n"
        "\n"
        "[compat.cursor]\n"
        "hooks = true\n"
        "\n"
        "[[marketplace.sources]]\n"
        'name = "example"\n'
    )
    merged = glc.merge_lean_compat(original)
    assert merged.count("[compat.claude]") == 1
    assert merged.count("[compat.cursor]") == 1
    assert glc.LEAN_START in merged
    data = tomllib.loads(merged)
    assert data["compat"]["claude"]["skills"] is True
    assert data["compat"]["claude"]["rules"] is False
    assert data["marketplace"]["sources"] == [{"name": "example"}]
    assert glc.lean_compat_applied(merged)
    again = glc.merge_lean_compat(merged)
    assert tomllib.loads(again) == data


def test_lock_retry_delay_backs_off():
    glc = _load("ce_glc_lock", ROOT / "grok_lean_config.py")
    install = _load("ce_install_lock", ROOT / "install.py")
    assert glc.lock_retry_delay(0) < glc.lock_retry_delay(1) < glc.lock_retry_delay(3)
    assert install.lock_retry_delay(0) < install.lock_retry_delay(2)
    hint = install._local_source_required_message()
    assert "<repo>/chaos-engine" in hint
    assert "install.py" in hint and "VERSION" in hint
    assert "lock_retry_delay(attempt)" in inspect.getsource(glc._config_lock)
    assert "lock_retry_delay(attempt)" in inspect.getsource(install.project_lock)


def test_grok_sync_failure_still_records_identity(tmp_path, monkeypatch):
    hosts = _load("ce_hosts_identity", ROOT / "hosts.py")
    calls = []

    def boom(project, uninstall=False):
        raise RuntimeError("sync failed")

    def identity(project):
        calls.append(project)
        return {"id": "kept"}

    monkeypatch.setattr(hosts, "sync_grok_user_lean_config", boom)
    monkeypatch.setattr(hosts, "ensure_project_identity", identity)
    receipt = {}
    hosts._record_grok_and_identity(receipt, tmp_path)
    assert calls == [tmp_path]
    assert receipt["identity"] == {"id": "kept"}
    assert "grokLeanConfig" not in receipt


def test_every_worker_gets_its_own_sandbox_and_byte_changes_fail():
    grok = _load("ce_tests_conftest", ROOT / "tests" / "conftest.py")
    scripts = _load("ce_scripts_conftest", ROOT / "tests" / "scripts" / "conftest.py")
    first = grok.grok_sandbox_env(
        {"CHAOS_ENGINE_PROTECTED_GROK_HOME": "/real/grok"},
        worker_id="gw0",
        real_home=Path("/real/grok"),
    )
    second = grok.grok_sandbox_env(
        {"CHAOS_ENGINE_PROTECTED_GROK_HOME": "/real/grok"},
        worker_id="gw1",
        real_home=Path("/real/grok"),
    )
    assert first["GROK_HOME"] != second["GROK_HOME"]
    assert grok.grok_byte_problems(b"before", b"after", b"")
    assert grok.grok_byte_problems(b"same", b"same", b"") == []
    env = {}
    one = scripts.assign_test_sandbox(env, "gw0")
    two = scripts.assign_test_sandbox(env, "gw1")
    assert one != two
    source = inspect.getsource(scripts.pytest_configure)
    assert source.index("protect(") < source.index("assign_test_sandbox")
    assert source.index("assign_test_sandbox") < source.index("return")
