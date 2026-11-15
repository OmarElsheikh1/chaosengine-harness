"""Console entry for the chaosengine-harness CLI.

Subcommands stay on install.py. An install one-liner flag set runs bootstrap.py.
"""

from __future__ import annotations

import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path


INSTALL_COMMANDS = frozenset(
    {
        "install",
        "status",
        "doctor",
        "rollback",
        "uninstall",
        "repair",
        "addons",
        "init",
        "upgrade",
        "bundle",
        "cache",
        "explain",
        "verify",
        "restore-edits",
    }
)
DEFAULT_REPOSITORY = "ShaftHQ/chaosengine-harness"


def target_for(argv: list[str]) -> str:
    """install.py for a subcommand, bootstrap.py for one-liner flags."""
    if argv and argv[0] in INSTALL_COMMANDS:
        return "install.py"
    return "bootstrap.py"


def bootstrap_args(argv: list[str], project: str) -> list[str]:
    """Forward flags unchanged and fill the repository and project when absent."""
    args = list(argv)
    if "--repository" not in args:
        args.extend(["--repository", DEFAULT_REPOSITORY])
    if "--project" not in args:
        args.extend(["--project", project])
    return args


def _python_candidates() -> list[list[str]]:
    found: list[list[str]] = []
    for name in ("python3", "python"):
        path = shutil.which(name)
        if path:
            found.append([path])
    py = shutil.which("py")
    if py:
        found.append([py, "-3"])
    return found


def _supports(command: list[str]) -> bool:
    probe = subprocess.run(
        [*command, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
        check=False,
        capture_output=True,
    )
    return probe.returncode == 0


def discover_python() -> list[str] | None:
    """python3, then python, then py -3. Each must be 3.11 or newer."""
    current = [sys.executable]
    if _supports(current):
        return current
    for command in _python_candidates():
        if _supports(command):
            return command
    return None


def main() -> int:
    root = Path(__file__).resolve().parent
    argv = sys.argv[1:]
    name = target_for(argv)
    target = root / name
    if not target.is_file():
        sys.stderr.write(f"chaosengine-harness: {name} is missing beside the console entry\n")
        return 1
    if name == "install.py":
        sys.argv = [str(target), *argv]
        try:
            runpy.run_path(str(target), run_name="__main__")
        except SystemExit as exit_:
            code = exit_.code
            if code is None or code == 0:
                return 0
            if isinstance(code, int):
                return code
            return 1
        return 0
    python = discover_python()
    if python is None:
        sys.stderr.write(
            "ChaosEngine requires Python 3.11 or newer. "
            "fix-next: install Python 3.11+ or the Windows py launcher.\n"
        )
        return 1
    completed = subprocess.run(
        [*python, str(target), *bootstrap_args(argv, os.getcwd())],
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
