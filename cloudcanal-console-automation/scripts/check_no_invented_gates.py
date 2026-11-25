#!/usr/bin/env python3
"""Fail when start-job checks a slot claim."""

import sys
from pathlib import Path


FORBIDDEN = (
    "assert_mini_slot_free",
    "Release that claim before start-job",
)


def files_from_args(argv):
    if len(argv) > 1:
        return [Path(argument) for argument in argv[1:]]
    root = Path(__file__).resolve().parents[1] / "scripts" / "cc_console"
    return [root / "datajob.py", root / "cli.py"]


def main(argv):
    problems = []
    for path in files_from_args(argv):
        if not path.is_file():
            print(f"missing path: {path}", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        for name in FORBIDDEN:
            if name in text:
                problems.append(f"{path}: contains {name}")
    if problems:
        print("Invented Console gates:", file=sys.stderr)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    print("start-job does not check a claim")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
