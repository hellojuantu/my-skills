#!/usr/bin/env python3
"""Fail when Console response code reads a second name for one field."""

import re
import sys
from pathlib import Path


GET_KEY = re.compile(r"""\.get\(\s*["']([A-Za-z_][A-Za-z0-9_]*)["']\s*\)""")
FOR_KEYS = re.compile(r"""for\s+key\s+in\s*\(([^)]*)\)""", re.S)
STRING_KEY = re.compile(r"""["']([A-Za-z_][A-Za-z0-9_]*)["']""")

# Names that are not fields on the Console value object. One hit is enough.
NEVER = {
    "fsmID",
    "fsm_id",
    "fsmInfo",
    "jobName",
    "sourceDataSource",
    "sourceDs",
    "targetDataSource",
    "targetDs",
    "errorMsg",
    "exceptionMsg",
    "currentStatus",
    "databaseName",
    "serviceName",
    "defaultDb",
    "ssl",
    "accountIdentifier",
    "warehouseName",
}

# Two of these on one line, or in one `for key in (...)`, are aliases.
GROUPS = (
    {"fsmId", "fsmID", "fsm_id", "fsmInfo"},
    {"dataJobName", "jobName"},
    {"sourceDsVO", "sourceDataSource", "sourceDs"},
    {"targetDsVO", "targetDataSource", "targetDs"},
    {"dataSourceType", "type"},
    {"deployType", "deployEnvType"},
    {"columnName", "column"},
    {"success", "pass"},
    {"dbName", "databaseName", "database", "defaultDb", "sid", "serviceName"},
    {"useSSL", "ssl"},
    {"warehouse", "warehouseName"},
    {"currTaskStatus", "currentStatus"},
    {"errorMsg", "exceptionMsg"},
)


def roots_from_args(argv):
    if len(argv) > 1:
        return [Path(argument) for argument in argv[1:]]
    return [Path(__file__).resolve().parents[1] / "scripts"]


def python_files(path):
    if path.is_file():
        return [path]
    return sorted(item for item in path.rglob("*.py") if item.is_file())


def group_hits(keys):
    found = []
    for group in GROUPS:
        overlap = sorted(group & set(keys))
        if len(overlap) > 1:
            found.append(", ".join(overlap))
    return found


def scan_text(path, text):
    problems = []
    for number, line in enumerate(text.splitlines(), 1):
        keys = GET_KEY.findall(line)
        never = sorted(set(keys) & NEVER)
        if never:
            problems.append(f"{path}:{number}: not a Console field: {', '.join(never)}")
        aliases = group_hits(keys)
        if aliases:
            problems.append(f"{path}:{number}: one value has several names: {'; '.join(aliases)}")
    for match in FOR_KEYS.finditer(text):
        keys = STRING_KEY.findall(match.group(1))
        aliases = group_hits(keys)
        if not aliases:
            continue
        line = text[: match.start()].count("\n") + 1
        problems.append(f"{path}:{line}: one value has several names: {'; '.join(aliases)}")
    return problems


def main(argv):
    problems = []
    for root in roots_from_args(argv):
        if not root.exists():
            print(f"missing path: {root}", file=sys.stderr)
            return 1
        for path in python_files(root):
            problems.extend(scan_text(path, path.read_text(encoding="utf-8")))
    if problems:
        print("Console field aliases:", file=sys.stderr)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    print("Console response reads use one field name")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
