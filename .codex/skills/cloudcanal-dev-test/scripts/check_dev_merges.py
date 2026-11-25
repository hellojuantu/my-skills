#!/usr/bin/env python3
"""Check that each project's HEAD contains the current remote dev branch."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import subprocess


DEV_REF = "refs/heads/dev"
GIT_TIMEOUT_SECONDS = 20


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_NO_LAZY_FETCH": "1",
        },
        timeout=GIT_TIMEOUT_SECONDS,
        text=True,
        errors="replace",
    )


def check(repo):
    try:
        remote = git(repo, "ls-remote", "--exit-code", "origin", DEV_REF)
        if remote.returncode == 2:
            return False, "origin has no dev branch"
        if remote.returncode:
            return False, "could not query origin dev; check the remote and authentication"

        fields = remote.stdout.split()
        if len(fields) != 2 or fields[1] != DEV_REF or not re.fullmatch(
            r"(?:[0-9a-f]{40}|[0-9a-f]{64})", fields[0]
        ):
            return False, "unexpected origin dev response"
        dev = fields[0]

        if git(repo, "cat-file", "-e", f"{dev}^{{commit}}").returncode:
            return False, f"origin dev {dev[:12]} is missing locally; run git fetch origin dev"

        ancestry = git(repo, "merge-base", "--is-ancestor", dev, "HEAD")
        if ancestry.returncode == 0:
            return True, f"HEAD contains origin dev {dev[:12]}"
        if ancestry.returncode == 1:
            return False, f"HEAD lacks origin dev {dev[:12]}; fetch and merge origin dev"
        return False, f"could not compare HEAD with origin dev {dev[:12]}"
    except subprocess.TimeoutExpired:
        return False, f"Git command timed out after {GIT_TIMEOUT_SECONDS} seconds"
    except OSError:
        return False, "could not run Git"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / "cc-all-in-one")
    args = parser.parse_args()

    root = args.root.expanduser()
    try:
        repos = sorted(
            path for path in root.iterdir()
            if path.is_dir() and ((path / ".git").is_dir() or (path / ".git").is_file())
        )
    except OSError:
        parser.exit(2, f"Could not read project root {root}\n")
    if not repos:
        parser.exit(2, f"No Git project directories found under {root}\n")

    failures = 0
    with ThreadPoolExecutor(max_workers=min(9, len(repos))) as executor:
        for repo, (passed, result) in zip(repos, executor.map(check, repos)):
            print(f"{'PASS' if passed else 'FAIL'} {repo.name}: {result}")
            failures += not passed

    print(f"{len(repos) - failures}/{len(repos)} projects passed, {failures} failed")
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
