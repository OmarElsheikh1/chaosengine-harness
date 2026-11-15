"""Issue 26: expected tool-name allowlist per published MCP server."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Tool names from maven-tools-mcp 3.2.4 (commit 78ed17446c6f50b454b3741359f57dddce70f687).
MAVEN_TOOLS_PINNED = frozenset(
    {
        "analyze_dependency_age",
        "analyze_pom_dependencies",
        "analyze_project_health",
        "analyze_release_patterns",
        "check_multiple_dependencies",
        "check_version_exists",
        "compare_dependency_versions",
        "get_latest_version",
        "recommend_pom_upgrades",
    }
)


def _policy():
    spec = importlib.util.spec_from_file_location("ce_mcp_probe_policy", ROOT / "mcp_policy.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_maven_tools_allowlist_matches_pinned_jar_tools():
    policy = _policy()
    table = getattr(policy, "EXPECTED_MCP_TOOL_NAMES", None)
    assert isinstance(table, dict)
    assert table.get("maven-tools-mcp") == MAVEN_TOOLS_PINNED


def test_allowlist_helper_names_extra_and_missing():
    policy = _policy()
    mismatch = getattr(policy, "tool_catalog_mismatch", None)
    assert callable(mismatch)
    full = set(policy.EXPECTED_MCP_TOOL_NAMES["maven-tools-mcp"])
    extra = mismatch("maven-tools-mcp", full | {"surprise-tool"})
    missing = mismatch("maven-tools-mcp", full - {"get_latest_version"})
    assert extra and "extra" in extra and "surprise-tool" in extra
    assert missing and "missing" in missing and "get_latest_version" in missing


def test_missing_declaration_fails_closed():
    policy = _policy()
    text = policy.tool_catalog_mismatch("not-a-published-server", ["some-tool"])
    assert text
    assert "no expected" in text.casefold()


def test_empty_allowlist_permits_no_tools():
    policy = _policy()
    empty = {"closed-server": frozenset()}
    assert policy.tool_catalog_mismatch("closed-server", [], allowlists=empty) is None
    text = policy.tool_catalog_mismatch("closed-server", ["a-tool"], allowlists=empty)
    assert text and "extra" in text and "a-tool" in text


def test_opt_in_servers_skip_with_a_reason_and_are_not_an_empty_allowlist():
    policy = _policy()
    assert callable(getattr(policy, "mcp_probe_skip_reason", None))
    for server in policy.OPTIONAL_MCP_IDS:
        reason = policy.mcp_probe_skip_reason(server)
        assert reason and reason.strip()
        declared = policy.EXPECTED_MCP_TOOL_NAMES.get(server, None)
        assert declared is None


def test_probe_spec_read_only_name_is_declared_and_negative_name_is_not():
    policy = _policy()
    spec = policy.mcp_stdio_probe_spec("maven-tools-mcp")
    assert isinstance(spec, dict)
    names = policy.EXPECTED_MCP_TOOL_NAMES["maven-tools-mcp"]
    read_only = spec["read_only"]["name"]
    negative = spec["negative"]["name"]
    assert read_only in names
    assert negative not in names
    assert read_only == "check_version_exists"
