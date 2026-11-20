"""Issue 23: maven-tools-mcp health probe consumes the tool allowlist."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, filename: str):
    path = ROOT / filename
    if not path.is_file() and "/" not in filename:
        nested = ROOT / "runtime" / filename
        if nested.is_file():
            path = nested
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _declared_names() -> set[str]:
    policy = _load("ce_mcp_probe_policy_for_maven", "mcp_policy.py")
    table = getattr(policy, "EXPECTED_MCP_TOOL_NAMES", None)
    if isinstance(table, dict) and isinstance(table.get("maven-tools-mcp"), frozenset):
        return set(table["maven-tools-mcp"])
    return {
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


def _probe():
    return _load("ce_maven_tools_probe", "packs/java/maven_tools.py").probe_maven_tools_runtime


def _process(lines: list[str]):
    process = mock.Mock()
    process.stdin = io.StringIO()
    process.stdout = io.StringIO("".join(f"{line}\n" for line in lines))
    process.stderr = io.StringIO()
    process.poll.return_value = None
    process.wait.return_value = 0
    return process


def _tools_line(names: set[str], *, log: bool = False) -> list[str]:
    tools = [{"name": name} for name in sorted(names)]
    listed = json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": tools}})
    prefix = ["2026-10-23T08:43:45.800Z DEBUG startup log"] if log else []
    return [
        *prefix,
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "maven-tools-mcp"}}}),
        '{"jsonrpc":"2.0","method":"notifications/message","params":{}}',
        listed,
    ]


def _call_lines() -> list[str]:
    ok = {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {"content": [{"type": "text", "text": "exists"}]},
    }
    refused = {
        "jsonrpc": "2.0",
        "id": 4,
        "error": {"code": -32602, "message": "unknown tool"},
    }
    return [json.dumps(ok), json.dumps(refused)]


def test_nonempty_tools_list_missing_one_declared_name_fails_probe():
    declared = _declared_names()
    live = declared - {"get_latest_version"}
    assert live
    process = _process(_tools_line(live))
    probe = _probe()
    assert probe(Path("/java"), Path("/tools.jar"), popen=lambda *_a, **_k: process) is False
    assert "get_latest_version" in probe.last_failure
    assert "missing" in probe.last_failure


def test_catalog_growth_fails_probe_with_the_extra_name():
    declared = _declared_names()
    process = _process(_tools_line(declared | {"surprise-tool"}) + _call_lines())
    probe = _probe()
    assert probe(Path("/java"), Path("/tools.jar"), popen=lambda *_a, **_k: process) is False
    assert "surprise-tool" in probe.last_failure
    assert "extra" in probe.last_failure


def test_expected_catalog_read_only_call_and_negative_refusal_pass():
    declared = _declared_names()
    process = _process(_tools_line(declared, log=True) + _call_lines())
    probe = _probe()
    assert probe(Path("/java"), Path("/tools.jar"), popen=lambda *_a, **_k: process) is True
    requests = [json.loads(line) for line in process.stdin.getvalue().splitlines()]
    methods = [item["method"] for item in requests]
    assert methods == [
        "initialize",
        "notifications/initialized",
        "tools/list",
        "tools/call",
        "tools/call",
    ]
    read_only = requests[3]["params"]
    assert read_only["name"] == "check_version_exists"
    assert read_only["arguments"] == {"dependency": "junit:junit", "version": "4.13.2"}
    assert requests[4]["params"]["name"] != "check_version_exists"


def test_negative_call_that_succeeds_fails_probe():
    declared = _declared_names()
    accepted = {
        "jsonrpc": "2.0",
        "id": 4,
        "result": {"content": [{"type": "text", "text": "ran"}]},
    }
    lines = _tools_line(declared) + [
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "exists"}]}}),
        json.dumps(accepted),
    ]
    process = _process(lines)
    probe = _probe()
    assert probe(Path("/java"), Path("/tools.jar"), popen=lambda *_a, **_k: process) is False
    assert "refus" in probe.last_failure.casefold()


def test_read_only_call_without_content_shape_fails_probe():
    declared = _declared_names()
    lines = _tools_line(declared) + [
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {"ok": True}}),
        json.dumps({"jsonrpc": "2.0", "id": 4, "error": {"code": -32601, "message": "no"}}),
    ]
    process = _process(lines)
    probe = _probe()
    assert probe(Path("/java"), Path("/tools.jar"), popen=lambda *_a, **_k: process) is False
    assert "read-only" in probe.last_failure


_NO_CONTEXT7 = "--spring.profiles.active=no-context7"


def test_probe_argv_sets_no_context7_before_stdio_and_pinned_catalog_passes():
    declared = _declared_names()
    assert "resolve_library_id" not in declared
    assert "query_docs" not in declared
    assert "scan_transitive_vulnerabilities" in declared
    assert len(declared) == 10
    process = _process(_tools_line(declared) + _call_lines())
    seen: list[list[str]] = []

    def popen(argv, **_kwargs):
        assert process.stdin.getvalue() == ""
        seen.append(list(argv))
        return process

    probe = _probe()
    assert probe(Path("/java"), Path("/tools.jar"), popen=popen) is True
    assert seen == [["/java", "-jar", "/tools.jar", _NO_CONTEXT7]]
    assert process.stdin.getvalue()


def test_context7_tool_names_fail_closed_on_the_pinned_catalog():
    declared = _declared_names()
    process = _process(_tools_line(declared | {"resolve_library_id", "query_docs"}))
    probe = _probe()
    assert probe(Path("/java"), Path("/tools.jar"), popen=lambda *_a, **_k: process) is False
    assert "resolve_library_id" in probe.last_failure
    assert "query_docs" in probe.last_failure
    assert "extra" in probe.last_failure


def test_resolve_maven_tools_command_sets_no_context7_profile():
    tool = _load("ce_tool_maven_no_context7", "tool.py")
    java = Path("/java")
    jar = Path("/tools.jar")
    original = tool.load_host_controller
    tool.load_host_controller = lambda _root: {
        "discover_maven_tools_runtime": lambda: (java, jar),
    }
    try:
        command = tool.resolve_maven_tools_command(Path("/installed"))
    finally:
        tool.load_host_controller = original
    assert command == [str(java), "-jar", str(jar), _NO_CONTEXT7]
