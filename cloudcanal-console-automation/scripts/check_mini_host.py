#!/usr/bin/env python3
"""Fail when script code hardcodes the Mini console host instead of reading mini.env."""

import re
import sys
from pathlib import Path


PATTERN = re.compile(r"https?://mini:|\{\s*[\"']mini[\"']\s*\}")
ROOTS = (
    "cloudcanal-console-automation/scripts",
    "cloudcanal-dev-test/scripts",
    "datasource-lab/scripts",
    ".codex/skills/cloudcanal-console-automation/scripts",
    ".codex/skills/cloudcanal-dev-test/scripts",
    ".codex/skills/datasource-lab/scripts",
)


def repo_root():
    return Path(__file__).resolve().parents[2]


def files_from_args(argv):
    if len(argv) > 1:
        return [Path(argument) for argument in argv[1:]]
    found = []
    for relative in ROOTS:
        root = repo_root() / relative
        if root.is_dir():
            found.extend(sorted(path for path in root.rglob("*.py") if path.is_file()))
    return found


def scan(path):
    problems = []
    text = path.read_text(encoding="utf-8")
    for number, line in enumerate(text.splitlines(), 1):
        if PATTERN.search(line):
            problems.append(f"{path}:{number}: Mini host is hardcoded. Read cloudcanal-dev-test/scripts/mini_names.py.")
    return problems


def main(argv):
    problems = []
    for path in files_from_args(argv):
        if not path.is_file():
            print(f"missing path: {path}", file=sys.stderr)
            return 1
        problems.extend(scan(path))
    if problems:
        print("Hardcoded Mini host:", file=sys.stderr)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    print("Mini console host comes from mini.env")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
