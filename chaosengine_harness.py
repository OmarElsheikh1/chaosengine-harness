"""Console entry for the chaosengine-harness CLI.

The installer stays install.py. This module only locates that file and runs it.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    install_py = Path(__file__).resolve().parent / "install.py"
    if not install_py.is_file():
        sys.stderr.write("chaosengine-harness: install.py is missing beside the console entry\n")
        return 1
    sys.argv[0] = str(install_py)
    try:
        runpy.run_path(str(install_py), run_name="__main__")
    except SystemExit as exit_:
        code = exit_.code
        if code is None or code == 0:
            return 0
        if isinstance(code, int):
            return code
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
