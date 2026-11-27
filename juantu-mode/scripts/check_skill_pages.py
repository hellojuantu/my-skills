#!/usr/bin/env python3
"""Fail when a skill page link misses its heading or a description leaves its line."""

import collections
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote


OWNED = (
    "AGENTS.md",
    "README.md",
    "juantu-mode",
    "cloudcanal-dev-test",
    "cloudcanal-console-automation",
    "datasource-lab",
)
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
FENCE = re.compile(r"^```")


def slug_text(text):
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    kept = []
    for char in text.strip().lower():
        category = unicodedata.category(char)
        if char in "- " or category.startswith(("L", "M", "N")) or category == "Pc":
            kept.append(char)
    return re.sub(r"\s+", "-", "".join(kept))


def heading_slugs(text):
    seen = collections.Counter()
    slugs = set()
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if not match:
            continue
        base = slug_text(match.group(2))
        count = seen[base]
        seen[base] += 1
        slugs.add(base if count == 0 else f"{base}-{count}")
    return slugs


def markdown_files(root):
    path = Path(root)
    if path.is_file():
        return [path] if path.suffix == ".md" else []
    return sorted(item for item in path.rglob("*.md") if item.is_file())


def owned_files(repo):
    files = []
    for name in OWNED:
        files.extend(markdown_files(repo / name))
    return files


def frontmatter_problems(path, text):
    if not text.startswith("---\n"):
        return []
    end = text.find("\n---", 3)
    if end == -1:
        return [f"{path}: Frontmatter does not close."]
    block = text[4:end]
    problems = []
    if "\n\n" in block:
        problems.append(f"{path}: Frontmatter contains a blank line.")
    for line in block.splitlines():
        if line.startswith("description:") and line.strip() == "description:":
            problems.append(f"{path}: Description must stay on one line.")
    return problems


def link_problems(path, text, files_by_path):
    problems = []
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LINK.finditer(line):
            target = match.group(2)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path_part, _, fragment = target.partition("#")
            fragment = unquote(fragment)
            dest = path if not path_part else (path.parent / path_part).resolve()
            if path_part and not dest.exists():
                problems.append(f"{path}: Link target is missing: {path_part}")
                continue
            if fragment and dest.suffix == ".md":
                slugs = heading_slugs(files_by_path.get(dest, dest.read_text(encoding="utf-8")))
                if fragment not in slugs:
                    shown = dest.name if dest == path else path_part
                    problems.append(f"{path}: Link #{fragment} does not match a heading in {shown}.")
    return problems


def check_files(files):
    texts = {}
    for path in files:
        texts[path.resolve()] = path.read_text(encoding="utf-8")
    problems = []
    for path, text in texts.items():
        problems.extend(frontmatter_problems(path, text))
        problems.extend(link_problems(path, text, texts))
    return problems


def main(argv):
    if len(argv) > 1:
        files = []
        for argument in argv[1:]:
            files.extend(markdown_files(argument))
    else:
        repo = Path(__file__).resolve().parents[2]
        files = owned_files(repo)
    problems = check_files(files)
    if problems:
        print("Skill pages are not usable:", file=sys.stderr)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    print(f"Skill pages resolve: {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
