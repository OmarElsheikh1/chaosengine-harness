"""Resolve a real Bash executable.

Windows CreateProcess searches System32 before PATH. System32\\bash.exe is the
WSL stub: it prints a UTF-16 message and exits 1 when no distribution is installed.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def posix_bash() -> str:
    override = os.environ.get("CHAOS_ENGINE_BASH")
    if override:
        if not Path(override).is_file():
            raise RuntimeError(f"CHAOS_ENGINE_BASH is not a file: {override}")
        return override
    if os.name == "nt":
        for candidate in (
            Path(r"C:\Program Files\Git\bin\bash.exe"),
            Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        ):
            if candidate.is_file():
                return str(candidate)
        raise RuntimeError("Git Bash is required on Windows. System32 bash is the WSL stub.")
    found = shutil.which("bash")
    if not found:
        raise RuntimeError("bash is required")
    return found
