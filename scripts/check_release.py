#!/usr/bin/env python3
"""Read-only, offline checks for the files intended for a public VGI release.

By default select tracked working-tree files with read-only Git commands. Use
--all-files for a source export without Git; local output/cache directories are
excluded in that mode. This is a finite policy and credential-pattern heuristic,
not proof of ownership, a complete secret detector, or a Git-history audit.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT_FILES = {
    ".gitignore", ".gitattributes", "LICENSE", "NOTICE", "README.md",
    "THIRD_PARTY_NOTICES.md", "CONTRIBUTING.md", "SECURITY.md",
    "CODE_OF_CONDUCT.md", "CHANGELOG.md", "pyproject.toml", "MANIFEST.in",
    "requirements-visual.txt",
}
SOURCE_ROOTS = {"urd", "vgi", "tests", "scripts", ".github", "docs", "examples"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".ps1", ".json"}
DATA_SUFFIXES = {".csv", ".jsonl", ".ppm"}
LOCAL_DIRECTORIES = {".git", ".venv", "venv", "__pycache__", ".pytest_cache",
                     "output", "local-sessions", "build", "dist"}
MAX_BYTES = 5 * 1024 * 1024
WINDOWS_USER = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+([^\\/\s\"'`]+)", re.I)
CREDENTIALS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)"
               r"\s*[=:]\s*['\"][A-Za-z0-9_./+~=-]{20,}['\"]"),
)


def selected_paths(root: Path, all_files: bool) -> list[Path]:
    if all_files:
        result = []
        for directory, directories, files in os.walk(root, followlinks=False):
            # Never descend into local game evidence, virtualenvs, or Git objects.
            directories[:] = sorted(name for name in directories
                                    if name not in LOCAL_DIRECTORIES
                                    and not name.endswith(".egg-info"))
            base = Path(directory)
            for name in list(directories):
                if (base / name).is_symlink():
                    result.append((base / name).relative_to(root))
                    directories.remove(name)
            result.extend((base / name).relative_to(root) for name in sorted(files))
        return sorted(result)
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                             capture_output=True, check=True)
        if Path(os.fsdecode(top.stdout).strip()).resolve() != root:
            raise ValueError("--root must be the repository root")
        files = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "-z"],
                               capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("tracked-file selection requires Git; use --all-files for a source export") from error
    return sorted(Path(os.fsdecode(name)) for name in files.stdout.split(b"\0") if name)


def marked_synthetic(directory: Path, root: Path, selected: set[Path]) -> bool:
    """An image/table needs a selected manifest/report declaring synthetic=true."""
    while directory != root:
        for name in ("session.json", "report.json"):
            marker = directory / name
            if marker.relative_to(root) not in selected or marker.is_symlink():
                continue
            try:
                if marker.stat().st_size > MAX_BYTES:
                    continue
                data = json.loads(marker.read_bytes())
                if isinstance(data, dict) and data.get("synthetic") is True:
                    return True
            except (OSError, ValueError):
                continue
        directory = directory.parent
    return False


def check_files(root: Path, paths: list[Path]) -> list[tuple[Path, str]]:
    findings = []
    selected = set(paths)
    for relative in paths:
        path = root / relative
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
            findings.append((relative, "symlink"))
            continue
        if relative.is_absolute() or ".." in relative.parts:
            findings.append((relative, "unapproved-path"))
            continue
        if relative.parts[0] not in SOURCE_ROOTS and relative.as_posix() not in ROOT_FILES:
            findings.append((relative, "unapproved-path"))
            continue
        suffix = relative.suffix.lower()
        is_example = relative.parts[0] == "examples"
        if relative.as_posix() not in ROOT_FILES and suffix not in TEXT_SUFFIXES | DATA_SUFFIXES:
            findings.append((relative, "unapproved-file-type"))
            continue
        if suffix in DATA_SUFFIXES and not is_example:
            findings.append((relative, "unapproved-file-type"))
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                findings.append((relative, "oversized-file"))
                continue
            content = path.read_bytes()
        except OSError:
            findings.append((relative, "unreadable-file"))
            continue
        if is_example and suffix in DATA_SUFFIXES and not marked_synthetic(path.parent, root, selected):
            findings.append((relative, "unmarked-example-data"))
        if suffix == ".ppm":
            if not content.startswith((b"P3\n", b"P6\n")):
                findings.append((relative, "invalid-ppm-header"))
            continue
        try:
            text = content.decode("utf-8-sig")
            if any(ord(character) < 32 and character not in "\t\n\r" for character in text):
                raise ValueError("control character")
        except (UnicodeError, ValueError):
            findings.append((relative, "non-text-content"))
            continue
        if any(not match.group(1).startswith("<") for match in WINDOWS_USER.finditer(text)):
            findings.append((relative, "personal-windows-path"))
        if any(pattern.search(text) for pattern in CREDENTIALS):
            findings.append((relative, "credential-pattern"))
        if is_example and suffix == ".json":
            try:
                data = json.loads(text)
                if not isinstance(data, dict) or data.get("synthetic") is not True:
                    findings.append((relative, "example-not-synthetic"))
            except ValueError:
                findings.append((relative, "invalid-example-json"))
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--all-files", action="store_true",
                        help="scan a source export, excluding local/cache directories (no Git required)")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if not root.is_dir():
            raise ValueError("--root must be an existing directory")
        paths = selected_paths(root, args.all_files)
        if not paths:
            raise ValueError("no release files selected")
        findings = check_files(root, paths)
    except (ValueError, OSError) as error:
        print(f"Release check error: {error}", file=sys.stderr)
        return 2
    # Never echo a matching line or value: diagnostics must not disclose a secret.
    for path, code in findings:
        print(f"{path.as_posix()}: {code}")
    if findings:
        print(f"Release check failed: {len(findings)} finding(s) in {len(paths)} selected files.")
        return 1
    print(f"Release check passed: {len(paths)} selected files; heuristic checks only, no history audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
