#!/usr/bin/env python3
"""One installer-contract cell. Exit 0 only when doctor passes.

Stdin is closed. The job timeout is the budget; child commands use a shorter
timeout. Upgrade keeps a sentinel memory record. Empty cells uninstall without
deleting that store. Graphify query and MemPalace search are the smoke, not
``--help``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TAG = "0.4.20261115.5"
HARNESS_REPO = "https://github.com/ShaftHQ/chaosengine-harness.git"
SHAFT_REPO = "https://github.com/ShaftHQ/SHAFT_ENGINE.git"
SENTINEL_NAME = "sentinel.txt"
SENTINEL = "chaos-engine-installer-contract-sentinel\n"


def _run(argv: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed


def _commit(source: Path, timeout: int) -> str:
    completed = _run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        cwd=source,
        timeout=timeout,
    )
    commit = completed.stdout.strip()
    if len(commit) != 40:
        raise SystemExit(f"source pin is not 40 hex: {commit}")
    return commit


def _prepare(context: str, framework: str, project: Path, workspace: Path, timeout: int) -> None:
    project.mkdir(parents=True, exist_ok=True)
    if context == "empty":
        return
    if context == "non-maven":
        (project / "README.md").write_text("existing project\n", encoding="utf-8")
        (project / "app.py").write_text("print('app')\n", encoding="utf-8")
        return
    if context == "maven-not-shaft":
        (project / "pom.xml").write_text(
            "<project><groupId>com.example</groupId><artifactId>demo</artifactId></project>\n",
            encoding="utf-8",
        )
        return
    if context == "consumer-shaft":
        (project / "pom.xml").write_text(
            "<project><groupId>io.github.shafthq</groupId>"
            "<artifactId>consumer</artifactId></project>\n",
            encoding="utf-8",
        )
        suffix = {"testng": "Test.java", "junit": "Test.java", "cucumber": "Steps.java"}.get(
            framework, "Test.java"
        )
        tests = project / "src" / "test" / "java"
        tests.mkdir(parents=True)
        (tests / f"Sample{suffix}").write_text("// framework marker\n", encoding="utf-8")
        return
    if context == "shaft-dev":
        if any(project.iterdir()):
            raise SystemExit("shaft-dev project must start empty")
        _run(
            ["git", "clone", "--depth", "1", SHAFT_REPO, str(project)],
            cwd=project.parent,
            timeout=timeout,
        )
        return
    if context == "harness-dev":
        if any(project.iterdir()):
            raise SystemExit("harness-dev project must start empty")
        _run(
            ["git", "clone", "--local", str(workspace), str(project)],
            cwd=project.parent,
            timeout=timeout,
        )
        return
    raise SystemExit(f"unknown context: {context}")


def _install(source: Path, commit: str, project: Path, timeout: int) -> None:
    _run(
        [
            sys.executable,
            str(source / "install.py"),
            "install",
            "--project",
            str(project),
            "--source",
            str(source),
            "--commit",
            commit,
        ],
        cwd=project,
        timeout=timeout,
    )


def _upgrade(source: Path, commit: str, project: Path, timeout: int) -> None:
    # The installed copy is the previous pin. The upgrade under test is this
    # checkout's install.py. The old pin cannot read the current capability policy.
    installer = source / "install.py"
    _run(
        [
            sys.executable,
            str(installer),
            "upgrade",
            "--project",
            str(project),
            "--source",
            str(source),
            "--commit",
            commit,
        ],
        cwd=project,
        timeout=timeout,
    )


def _doctor(project: Path, timeout: int) -> None:
    _run(
        [
            sys.executable,
            str(project / ".chaos-engine" / "install.py"),
            "doctor",
            "--project",
            str(project),
        ],
        cwd=project,
        timeout=timeout,
    )


def _smoke(project: Path, timeout: int) -> None:
    tool = project / ".chaos-engine" / "tool.py"
    _run(
        [sys.executable, str(tool), "graphify", "query", "chaos-engine"],
        cwd=project,
        timeout=timeout,
    )
    _run(
        [sys.executable, str(tool), "mempalace", "search", "chaos-engine"],
        cwd=project,
        timeout=timeout,
    )


def _write_sentinel(project: Path) -> None:
    memory = project / ".memory"
    memory.mkdir(parents=True, exist_ok=True)
    (memory / SENTINEL_NAME).write_text(SENTINEL, encoding="utf-8")


def _assert_sentinel(project: Path) -> None:
    path = project / ".memory" / SENTINEL_NAME
    if not path.is_file() or path.read_text(encoding="utf-8") != SENTINEL:
        raise SystemExit("sentinel memory record missing")


def _clone_tag(destination: Path, timeout: int) -> None:
    _run(
        ["git", "clone", "--depth", "1", "--branch", TAG, HARNESS_REPO, str(destination)],
        cwd=destination.parent,
        timeout=timeout,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("fresh", "upgrade"))
    parser.add_argument("--context", required=True)
    parser.add_argument("--framework", default="none")
    parser.add_argument("--timeout-minutes", type=int, default=15)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    budget = max(60, args.timeout_minutes * 60 - 90)
    workspace = args.workspace.resolve()
    parent = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
    with tempfile.TemporaryDirectory(prefix="installer-contract-", dir=parent) as temporary:
        root = Path(temporary)
        project = root / "project"
        _prepare(args.context, args.framework, project, workspace, budget)
        if args.mode == "upgrade":
            if args.context == "harness-dev":
                # The pinned tag refuses a project that is a clone of this repo.
                _install(workspace, _commit(workspace, 60), project, budget)
            else:
                pinned = root / "pinned-source"
                _clone_tag(pinned, budget)
                _install(pinned, _commit(pinned, 60), project, budget)
            _write_sentinel(project)
            _upgrade(workspace, _commit(workspace, 60), project, budget)
            _assert_sentinel(project)
        else:
            _install(workspace, _commit(workspace, 60), project, budget)
        _doctor(project, budget)
        _smoke(project, min(budget, 180))
        if args.mode == "upgrade":
            _upgrade(workspace, _commit(workspace, 60), project, budget)
            _assert_sentinel(project)
        else:
            _install(workspace, _commit(workspace, 60), project, budget)
        _doctor(project, budget)
        if args.context == "empty":
            _write_sentinel(project)
            _run(
                [
                    sys.executable,
                    str(project / ".chaos-engine" / "install.py"),
                    "uninstall",
                    "--project",
                    str(project),
                ],
                cwd=project,
                timeout=budget,
            )
            _assert_sentinel(project)
            if (project / ".chaos-engine").exists():
                raise SystemExit("uninstall left the overlay in place")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
