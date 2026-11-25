#!/usr/bin/env python3
"""Check argument comments and the closing line of changed Java // calls."""

import argparse
from pathlib import Path
import re
import subprocess
import sys


JAVA_LEXEME = re.compile(
    r'//[^\n]*|/\*[\s\S]*?\*/|"""(?:\\[\s\S]|(?!""")[^\\])*"""|"(?:\\.|[^"\\\n])*"'
    r"|'(?:\\.|[^'\\\n])*'|(?P<opening>\( //)[ \t]*$", re.MULTILINE
)


def call_starts(source):
    line = 0
    previous = 0
    for token in JAVA_LEXEME.finditer(source):
        if token.lastgroup == "opening":
            line += source.count("\n", previous, token.start())
            previous = token.start()
            yield line


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git failed")
    return result.stdout


def added_lines(diff):
    """Map a repo-relative Java path to new-file line numbers introduced by the diff."""
    current = None
    new_line = 0
    added = {}
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            path = raw[6:].rstrip("\t")
            current = path if path.endswith(".java") else None
            continue
        if raw.startswith("@@"):
            # @@ -l,s +l,s @@
            plus = raw.split(" ")[2]
            new_line = int(plus[1:].split(",")[0])
            continue
        if current is None or raw.startswith("\\"):
            continue
        if raw.startswith("+"):
            added.setdefault(current, set()).add(new_line)
            new_line += 1
        elif raw.startswith("-"):
            continue
        else:
            new_line += 1
    return added


def call_violation(lines, start):
    index = start + 1
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped == ");":
            return None
        if stripped.endswith(" //"):
            index += 1
            continue
        return index, (
            "End every argument with // and put ');' on its own line: "
            + stripped
        )
    return start, "Unclosed // call"


def violations(repo, diff, untracked):
    found = []
    touched = added_lines(diff)
    for path in untracked:
        if path.endswith(".java"):
            text = (repo / path).read_text(encoding="utf-8", errors="replace")
            touched.setdefault(path, set()).update(range(1, text.count("\n") + 2))
    for path, numbers in sorted(touched.items()):
        file_path = repo / path
        if not file_path.is_file():
            continue
        source = file_path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        for start in call_starts(source):
            violation = call_violation(lines, start)
            if violation is None:
                continue
            line_index, message = violation
            if (line_index + 1) not in numbers and (start + 1) not in numbers:
                continue
            found.append(f"{path}:{line_index + 1}: {message}")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo = args.repo.resolve()
    diff = git(repo, "diff", "HEAD", "--unified=3")
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z", "--", "*.java").split("\0")
    found = violations(repo, diff, untracked)
    if found:
        print("\n".join(found), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
