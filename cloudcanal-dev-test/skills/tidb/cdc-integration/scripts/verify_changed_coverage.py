#!/usr/bin/env python3
"""Require 100% JaCoCo line coverage on changed executable Java lines."""

import argparse
from collections import defaultdict
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--base", default="HEAD")
    return parser.parse_args()


def git(repo, *args):
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    )
    return result.stdout


def changed_lines(repo, source_root, base):
    relative_root = source_root.resolve().relative_to(repo.resolve()).as_posix()
    output = git(repo, "diff", "--unified=0", "--no-ext-diff", base, "--", relative_root)
    result = defaultdict(set)
    current = None
    for line in output.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            if path == "/dev/null":
                current = None
            elif path.startswith("b/"):
                current = path[2:]
            else:
                current = path
            continue
        match = HUNK.match(line)
        if current is None or match is None:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        result[current].update(range(start, start + count))

    untracked = git(
        repo, "ls-files", "--others", "--exclude-standard", "--", relative_root
    )
    for path_text in untracked.splitlines():
        path = repo / path_text
        if path.suffix != ".java":
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        result[path_text].update(range(1, line_count + 1))
    return result


def jacoco_lines(report, repo, source_root):
    root = ET.parse(report).getroot()
    relative_root = source_root.resolve().relative_to(repo.resolve())
    result = {}
    for package in root.iter("package"):
        package_name = package.attrib.get("name", "")
        for source_file in package.findall("sourcefile"):
            path = relative_root / package_name / source_file.attrib["name"]
            lines = {}
            for line in source_file.findall("line"):
                number = int(line.attrib["nr"])
                lines[number] = {
                    key: int(line.attrib.get(key, 0))
                    for key in ("mi", "ci", "mb", "cb")
                }
            result[path.as_posix()] = lines
    return result


def main():
    args = parse_args()
    repo = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    source_root = args.source_root if args.source_root.is_absolute() else repo / args.source_root
    report = args.report if args.report.is_absolute() else repo / args.report
    if not report.is_file():
        raise SystemExit(f"JaCoCo XML not found: {report}")

    changed = changed_lines(repo, source_root, args.base)
    coverage = jacoco_lines(report, repo, source_root)
    executable = 0
    uncovered = []
    missing_sources = []
    covered_branches = 0
    missed_branches = 0
    for path in sorted(changed):
        if not changed[path]:
            continue
        if path not in coverage:
            missing_sources.append(path)
            continue
        covered_lines = coverage.get(path, {})
        for number in sorted(changed[path]):
            counters = covered_lines.get(number)
            if counters is None:
                continue
            executable += 1
            covered_branches += counters["cb"]
            missed_branches += counters["mb"]
            if counters["ci"] == 0:
                uncovered.append((path, number, counters))

    print(f"Changed executable lines: {executable}")
    if executable == 0:
        print("No changed executable Java lines found", file=sys.stderr)
        return 1
    if missing_sources:
        print("Changed Java files missing from JaCoCo XML:", file=sys.stderr)
        for path in missing_sources:
            print(f"  {path}", file=sys.stderr)
    if uncovered:
        print("Changed executable lines without coverage:", file=sys.stderr)
        for path, number, counters in uncovered:
            print(
                f"  {path}:{number} missed_instructions={counters['mi']}",
                file=sys.stderr,
            )
    if missing_sources or uncovered:
        return 1

    print("Changed executable-line coverage: 100%")
    total_branches = covered_branches + missed_branches
    if total_branches > 0:
        branch_percentage = covered_branches * 100.0 / total_branches
        print(
            f"Changed-line branch coverage (informational): "
            f"{covered_branches}/{total_branches} ({branch_percentage:.2f}%)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
