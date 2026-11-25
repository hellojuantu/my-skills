#!/usr/bin/env python3
"""Check the QA outline and wording of newly introduced support entries."""

import argparse
from collections import Counter
from difflib import unified_diff
from pathlib import Path
import re
import sys


FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+|$)")
SETEXT = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
PARAGRAPH_BREAK = re.compile(
    r"^(?: {4}| {0,3}\t| {0,3}(?:>|(?:[-+*]|[0-9]{1,9}[.)])(?:[ \t]+|$)"
    r"|(?:\*[ \t]*){3,}$|(?:-[ \t]*){3,}$|(?:_[ \t]*){3,}$))"
)
SUMMARY_SECTIONS = {"## 需求", "## 修复"}
TOP_LEVEL_BULLET = re.compile(r"^[-+*][ \t]+(.+)$")
FIRST_CLAUSE_END = re.compile(r"[，。；！？：,;!?:]")
SUPPORT_VERB = re.compile(r"支持(?=[ \t]+[A-Za-z`]|配置)")
OTHER_ACTIONS = ("修复", "解决", "开放", "新增", "优化", "调整", "移除")
SUPPORT_QUALIFIERS = ("不", "未", "不再", "停止", "取消", "移除", "仅", "只")


def outline(markdown):
    entries = []
    fence = None
    paragraph = []
    for line in markdown.splitlines():
        stripped = line.strip()
        opening = not entries and bool(stripped)
        if opening:
            entries.append(stripped)

        marker = FENCE.match(line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1]
            paragraph.clear()
        elif HEADING.match(line):
            if not opening:
                entries.append(stripped)
            paragraph.clear()
        elif paragraph and SETEXT.match(line):
            entries.extend(paragraph)
            entries.append(stripped)
            paragraph.clear()
        elif not stripped or PARAGRAPH_BREAK.match(line):
            paragraph.clear()
        else:
            paragraph.append(stripped)

    return entries


def summary_items(markdown):
    section = ""
    fence = None
    for number, line in enumerate(markdown.splitlines(), start=1):
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        if HEADING.match(line):
            section = line.strip()
        item = TOP_LEVEL_BULLET.match(line)
        if section in SUMMARY_SECTIONS and item:
            yield section, number, item[1].strip()


def misplaced_support(text):
    clause = FIRST_CLAUSE_END.split(text, maxsplit=1)[0]
    if clause.startswith(("支持", *OTHER_ACTIONS)):
        return False
    verb = SUPPORT_VERB.search(clause)
    return verb is not None and not clause[:verb.start()].rstrip().endswith(SUPPORT_QUALIFIERS)


def check_support_entries(original, candidate, candidate_path):
    existing = Counter((section, text) for section, _, text in summary_items(original))
    passed = True
    for section, number, text in summary_items(candidate):
        item = (section, text)
        if existing[item]:
            existing[item] -= 1
        elif misplaced_support(text):
            print(f"{candidate_path}:{number}: 新增支持条目请以「支持」开头，例如「支持 TiDB 源端和目标端配置 JDBC 连接时区」。", file=sys.stderr)
            passed = False
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path, help="untouched user-provided Markdown")
    parser.add_argument("candidate", type=Path, help="updated QA Markdown")
    parser.add_argument("--original", type=Path, help="pre-edit draft when the template only contains headings")
    args = parser.parse_args()

    try:
        template_text = args.template.read_text(encoding="utf-8-sig")
        candidate_text = args.candidate.read_text(encoding="utf-8-sig")
        original_text = args.original.read_text(encoding="utf-8-sig") if args.original else template_text
    except (OSError, UnicodeError) as error:
        parser.exit(2, f"Could not read Markdown files. {error}\n")

    template = outline(template_text)
    candidate = outline(candidate_text)
    if not template:
        parser.exit(2, "The QA template is empty. Use the original Markdown.\n")
    if candidate != template:
        print("Restore the opening line and section headings from the original QA template.", file=sys.stderr)
        for line in unified_diff(template, candidate, "original QA template", "updated QA", lineterm=""):
            print(line, file=sys.stderr)
        return 1
    if not check_support_entries(original_text, candidate_text, args.candidate):
        return 1

    print("QA opening line and section headings match the original template.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
