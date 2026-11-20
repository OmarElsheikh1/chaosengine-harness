#!/usr/bin/env python3
"""Assemble the portable ChaosEngine Agent Plugin from this repository."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # nosec B404 - fixed local git commands, no shell.
import zipfile
from pathlib import Path

SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
REPOSITORY = "https://github.com/ShaftHQ/chaosengine-harness"
DESCRIPTION = "Neutral project-local software agent working harness."
AUTHOR = {"name": "ChaosEngine contributors", "url": REPOSITORY}
# SHAFT scripts/agents/*.py are not in this repo. Do not copy them.
# The zipapp is tool.py plus distributions.json portable runtimeFiles.
RUNTIME_ENTRY = Path("tool.py")
RUNTIME_MAIN = b"import tool\nraise SystemExit(tool.main())\n"
PORTABLE_SOURCE_SUFFIXES = {
    ".md",
    ".LICENSE",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".svg",
    ".js",
    ".ps1",
    ".sh",
    ".txt",
}
BARE_NAMES = {"LICENSE", "keep-out.txt", "VERSION"}
ORIGIN_ONLY_ROOT_FILES = frozenset(
    {
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "CHANGELOG.md",
        "ROADMAP.md",
    }
)
OMITTED_ROOTS = frozenset({"tests", ".github", "scripts", "agent-plugins", "bin", "docs"})
RELEASE_FILES = (
    (Path("LICENSE"), Path("LICENSE")),
    (Path("agent-plugins/chaos-engine/CHANGELOG.md"), Path("CHANGELOG.md")),
    (Path("agent-plugins/chaos-engine/COMPATIBILITY.md"), Path("COMPATIBILITY.md")),
)


def git_executable() -> str:
    """Find Git before the fixed repository inventory command."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("Git is required to assemble the portable plugin")
    return executable


def engine_version(root: Path) -> str:
    """Return the harness VERSION, which is the plugin version."""
    path = root / "VERSION"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def require_contained(root: Path, candidate: Path, label: str) -> Path:
    """Resolve one source path and reject a link that leaves its root."""
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError) as error:
        raise ValueError(f"{label} must stay inside canonical skill sources: {candidate}") from error
    return resolved


def include_source(relative: Path) -> bool:
    """Portable payload only. Same omit idea as bootstrap.omitted_source_relative."""
    parts = relative.parts
    if not parts or parts[0] in OMITTED_ROOTS:
        return False
    if parts[:2] in {("assets", "brand"), ("packs", "shaft"), ("profiles", "shaft")}:
        return False
    if parts[0] == "shaft-skills":
        return False
    if relative.as_posix() in ORIGIN_ONLY_ROOT_FILES:
        return False
    return relative.suffix in PORTABLE_SOURCE_SUFFIXES or relative.name in BARE_NAMES


def tracked_source_files(repository_root: Path) -> set[Path]:
    """Return the reviewed files permitted to enter the package."""
    result = subprocess.run(
        [git_executable(), "ls-files", "-z"],
        cwd=repository_root,
        check=True,
        capture_output=True,  # nosec B603 - fixed git command, shell disabled.
    )
    return {
        repository_root / Path(path.decode("utf-8"))
        for path in result.stdout.split(b"\0")
        if path
    }


def tracked_release_file(repository_root: Path, relative: Path) -> Path:
    """Return a tracked regular file without following repository links."""
    candidate = repository_root / relative
    if not candidate.is_file():
        raise ValueError(f"missing source: {relative.as_posix()}")
    current = candidate
    while current != repository_root:
        if current.is_symlink():
            raise ValueError(f"release file must not be a symlink: {relative.as_posix()}")
        current = current.parent
    source = require_contained(repository_root, candidate, f"release file {relative.as_posix()}")
    if not source.is_file():
        raise ValueError(f"release file must be a file: {relative.as_posix()}")
    tracked = subprocess.run(
        [git_executable(), "ls-files", "--error-unmatch", "--", relative.as_posix()],
        cwd=repository_root,
        capture_output=True,  # nosec B603 - fixed git command, shell disabled.
    )
    if tracked.returncode:
        raise ValueError(f"release file must be tracked: {relative.as_posix()}")
    return source


def declared_runtime_sources(repository_root: Path) -> list[Path]:
    """tool.py plus the portable runtimeFiles list. A bad manifest names itself."""
    manifest = repository_root / "distributions.json"
    if not manifest.is_file():
        raise ValueError("missing runtime source: distributions.json")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        files = payload["distributions"]["portable"]["runtimeFiles"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError("missing runtime source: distributions.json") from error
    if not isinstance(files, list):
        raise ValueError("missing runtime source: distributions.json")
    sources: list[Path] = []
    for item in (RUNTIME_ENTRY.as_posix(), *files):
        if not isinstance(item, str) or not item or item in {path.as_posix() for path in sources}:
            if not isinstance(item, str) or not item:
                raise ValueError("missing runtime source: distributions.json")
            continue
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"runtime source must stay inside the repository: {item}")
        sources.append(relative)
    return sources


def required_runtime(repository_root: Path) -> list[Path]:
    """Resolve every required runtime file or name the one that is absent."""
    ready: list[Path] = []
    for relative in declared_runtime_sources(repository_root):
        if not (repository_root / relative).is_file():
            raise ValueError(f"missing runtime source: {relative.as_posix()}")
        ready.append(tracked_release_file(repository_root, relative))
    return ready


def output_overlaps_sources(repository_root: Path, package_root: Path) -> bool:
    package = package_root.resolve()
    root = repository_root.resolve()
    return package == root or root in package.parents or package in root.parents


def _json(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_manifests(package_root: Path, version: str) -> None:
    """Write discovery manifests. Bytes are stable across builds."""
    (package_root / "plugin.json").write_text(
        _json(
            {
                "$schema": SCHEMA_URL,
                "name": "chaos-engine",
                "version": version,
                "description": DESCRIPTION,
                "author": AUTHOR,
                "repository": REPOSITORY,
                "license": "MIT",
            }
        ),
        encoding="utf-8",
    )
    claude = package_root / ".claude-plugin"
    claude.mkdir()
    (claude / "plugin.json").write_text(
        _json(
            {
                "name": "chaos-engine",
                "version": version,
                "description": DESCRIPTION,
                "author": {"name": AUTHOR["name"]},
            }
        ),
        encoding="utf-8",
    )
    (claude / "marketplace.json").write_text(
        _json(
            {
                "name": "chaos-engine",
                "owner": {"name": AUTHOR["name"]},
                "description": DESCRIPTION,
                "plugins": [
                    {
                        "name": "chaos-engine",
                        "source": "./",
                        "description": DESCRIPTION,
                        "version": version,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    codex = package_root / ".codex-plugin"
    codex.mkdir()
    (codex / "plugin.json").write_text(
        _json(
            {
                "name": "chaos-engine",
                "version": version,
                "description": DESCRIPTION,
                "author": AUTHOR,
                "repository": REPOSITORY,
                "license": "MIT",
                "skills": "./skills/",
                "mcpServers": "./.mcp.json",
                "interface": {
                    "displayName": "ChaosEngine",
                    "shortDescription": "Neutral project working harness",
                    "longDescription": (
                        "A neutral project-local harness for research, planning, "
                        "implementation, verification, and durable learning."
                    ),
                    "developerName": AUTHOR["name"],
                    "category": "Developer Tools",
                    "capabilities": ["Instructions", "MCP servers"],
                    "defaultPrompt": ["Use ChaosEngine for this task."],
                },
            }
        ),
        encoding="utf-8",
    )
    (package_root / ".mcp.json").write_text(
        _json(
            {
                "mcpServers": {
                    "chaosengine": {
                        "command": "python3",
                        "args": ["./bin/chaos-engine.pyz", "mcp"],
                        "cwd": ".",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    marketplace = package_root / ".agents/plugins"
    marketplace.mkdir(parents=True)
    (marketplace / "marketplace.json").write_text(
        _json(
            {
                "name": "chaos-engine",
                "plugins": [
                    {"name": "chaos-engine", "source": {"source": "local", "path": "./"}}
                ],
            }
        ),
        encoding="utf-8",
    )


def copy_portable_tree(repository_root: Path, package_root: Path, allowed: set[Path]) -> None:
    """Copy tracked portable sources. Untracked files and symlinks stay out."""
    files = sorted(
        path
        for path in allowed
        if include_source(path.relative_to(repository_root))
    )
    for path in files:
        relative = path.relative_to(repository_root)
        if path.is_symlink():
            raise ValueError(f"canonical source must not be a symlink: {relative.as_posix()}")
        source = require_contained(repository_root, path, f"canonical source {relative.as_posix()}")
        if not source.is_file():
            continue
        target = package_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def copy_release_files(repository_root: Path, package_root: Path) -> None:
    for relative, target in RELEASE_FILES:
        shutil.copyfile(tracked_release_file(repository_root, relative), package_root / target)


def build_runtime(repository_root: Path, package_root: Path) -> None:
    """Build a deterministic stdlib zipapp from the required runtime files."""
    destination = package_root / "bin/chaos-engine.pyz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    entries = [("__main__.py", RUNTIME_MAIN)]
    for relative in declared_runtime_sources(repository_root):
        source = tracked_release_file(repository_root, relative)
        entries.append((relative.as_posix(), source.read_bytes().replace(b"\r\n", b"\n")))
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(entries):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_STORED
            archive.writestr(entry, content)


def assemble(repository_root: Path, package_root: Path, version: str | None = None) -> None:
    """Create one new portable package. Refuses to overwrite or leave the repo."""
    repository_root = Path(repository_root).resolve()
    package_root = Path(package_root)
    found = engine_version(repository_root)
    if not found:
        raise ValueError("VERSION has no harness version")
    if version is not None and version != found:
        raise ValueError(f"chaos-engine version must match the repository: {found}")
    if output_overlaps_sources(repository_root, package_root):
        raise ValueError("package output must not overlap canonical skill sources")
    if package_root.exists():
        raise FileExistsError(f"refusing to overwrite package output: {package_root}")
    required_runtime(repository_root)
    allowed = tracked_source_files(repository_root)
    skill = repository_root / "skills/chaos-engine/SKILL.md"
    if skill not in allowed:
        raise ValueError("canonical skill must be tracked: skills/chaos-engine/SKILL.md")
    for relative, _target in RELEASE_FILES:
        tracked_release_file(repository_root, relative)
    package_root.mkdir(parents=True)
    write_manifests(package_root, found)
    copy_portable_tree(repository_root, package_root, allowed)
    copy_release_files(repository_root, package_root)
    build_runtime(repository_root, package_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new package output directory")
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--version")
    arguments = parser.parse_args(argv)
    assemble(arguments.repository_root, arguments.output, arguments.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
