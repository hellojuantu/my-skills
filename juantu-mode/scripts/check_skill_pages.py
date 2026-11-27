#!/usr/bin/env python3
"""Fail when a skill page link misses its heading or a description leaves its line."""

import re
import sys
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
PUNCTUATION = re.compile(r"""[\u2000-\u206F\u2E00-\u2E7F\\'!"#$%&()*+,./:;<=>?@\[\]^`{|}~]""")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
ATX = re.compile(r"^ {0,3}#{1,6}[ \t]+(.+?)[ \t]*$")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
INLINE_LINK = re.compile(r"(?<!!)\[([^\]]+)\]\(\s*<?([^)\s>]+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)")
REFERENCE_USE = re.compile(r"(?<!!)\[([^\]]+)\]\[([^\]]*)\]")
REFERENCE_DEF = re.compile(r"^ {0,3}\[([^\]]+)\]:[ \t]+(\S+)")
CODE_SPAN = re.compile(r"`+[^`\n]*`+")
COMMENT = re.compile(r"<!--.*?-->", re.S)


class Slugger:
    def __init__(self):
        self.occurrences = {}

    def slug(self, value):
        text = re.sub(r"`([^`]*)`", r"\1", value)
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
        slug = PUNCTUATION.sub("", text.lower().strip())
        slug = re.sub(r"\s", "-", slug)
        original = slug
        while slug in self.occurrences:
            self.occurrences[original] += 1
            slug = original + "-" + str(self.occurrences[original])
        self.occurrences[slug] = 0
        return slug


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


def body(text):
    if text.startswith("---\n"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    return COMMENT.sub("", text)


def heading_slugs(text):
    slugs = set()
    slugger = Slugger()
    in_fence = False
    previous = ""
    for line in body(text).splitlines():
        marker = FENCE.match(line)
        if marker:
            in_fence = not in_fence
            previous = ""
            continue
        if in_fence:
            continue
        underline = SETEXT.match(line)
        if underline and previous.strip() and not previous.lstrip().startswith("#"):
            slugs.add(slugger.slug(previous.strip()))
            previous = ""
            continue
        match = ATX.match(line)
        if match:
            heading = re.sub(r"[ \t]+#+\s*$", "", match.group(1))
            slugs.add(slugger.slug(heading))
        previous = line
    return slugs


def visible_lines(text):
    lines = []
    in_fence = False
    for line in body(text).splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return lines


def link_targets(text):
    lines = visible_lines(text)
    definitions = {}
    for line in lines:
        definition = REFERENCE_DEF.match(line)
        if definition:
            definitions[definition.group(1).casefold()] = definition.group(2)
    targets = []
    for line in lines:
        visible = CODE_SPAN.sub(" ", line)
        for match in INLINE_LINK.finditer(visible):
            targets.append(match.group(2))
        for match in REFERENCE_USE.finditer(visible):
            label = match.group(2) or match.group(1)
            target = definitions.get(label.casefold())
            if target:
                targets.append(target)
    return targets


def frontmatter_problems(path, text):
    if not text.startswith("---\n"):
        return []
    end = text.find("\n---", 3)
    if end == -1:
        return [f"{path}: Frontmatter does not close."]
    lines = text[4:end].splitlines()
    problems = []
    if "" in lines:
        problems.append(f"{path}: Frontmatter contains a blank line.")
    for index, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        value = line.split(":", 1)[1].strip()
        continued = index + 1 < len(lines) and lines[index + 1][:1].isspace()
        if not value or value.startswith((">", "|")) or continued:
            problems.append(f"{path}: Description must stay on one line.")
    return problems


def link_problems(path, text, files_by_path):
    problems = []
    for target in link_targets(text):
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
