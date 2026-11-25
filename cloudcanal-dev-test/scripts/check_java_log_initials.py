#!/usr/bin/env python3
import argparse
from collections import Counter
import re
import subprocess
from pathlib import Path


JAVA_TOKEN = re.compile(
    r'//[^\r\n]*|/\*[\s\S]*?\*/|"""[\s\S]*?"""|"(?:\\.|[^"\\\r\n])*"'
    r"|'(?:\\.|[^'\\\r\n])*'|[A-Za-z_$][\w$]*|\S"
)
MESSAGE_PREFIX = re.compile(r"(?:\[[^\]\r\n]*\]|\\[nrtfs]|[^A-Za-z\\])*")
BRACKET_LABEL = re.compile(r'"(?:[ \t]*\[[^\]\r\n]+\])+[ \t]*"')
ENGLISH_WORD = re.compile(r"[a-z][A-Za-z0-9_]*")
LOG_LEVELS = {"trace", "debug", "info", "warn", "error"}


def message_literal(tokens, start):
    if tokens[start:start + 4] == ["String", ".", "format", "("]:
        start += 4
    if start < len(tokens) and tokens[start].startswith('"'):
        return start
    return None


def log_message(tokens, start, scopes, label_literals):
    literal = message_literal(tokens, start)
    if literal is not None or start >= len(tokens):
        return literal

    name = tokens[start]
    following = tokens[start + 1:start + 2]
    for scope in reversed(scopes):
        if name in scope:
            value = scope[name]
            if following == ["+"] and value in label_literals:
                return message_literal(tokens, start + 2)
            return value if following in ([","], [")"]) else None

    if following == [","] and re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
        return message_literal(tokens, start + 2)
    return None


def lowercase_initials(source):
    matches = [match for match in JAVA_TOKEN.finditer(source) if not match[0].startswith(("//", "/*"))]
    tokens = [match[0] for match in matches]
    declarations = Counter(tokens[i + 1] for i, token in enumerate(tokens[:-1]) if token == "String")
    label_literals = set()
    scopes = [{}]
    violations = {}
    for index, token in enumerate(tokens):
        if token == "{":
            scopes.append({})
        elif token == "}" and len(scopes) > 1:
            scopes.pop()
        elif token == "String" and tokens[index + 2:index + 3] == ["="]:
            name = tokens[index + 1]
            scopes[-1][name] = message_literal(tokens, index + 3)
            modifier = index - 1
            while modifier >= 0 and tokens[modifier] in {"private", "public", "protected", "static", "transient"}:
                modifier -= 1
            if (modifier >= 0 and tokens[modifier] == "final" and declarations[name] == 1
                    and tokens[index + 4:index + 5] == [";"] and BRACKET_LABEL.fullmatch(tokens[index + 3])):
                label_literals.add(index + 3)
        elif tokens[index + 1:index + 2] == ["="] and any(token in scope for scope in scopes):
            scopes[-1][token] = message_literal(tokens, index + 2)
        elif (token.lower() in {"log", "logger"} and index + 3 < len(tokens)
              and tokens[index + 1] == "." and tokens[index + 2] in LOG_LEVELS and tokens[index + 3] == "("):
            literal = log_message(tokens, index + 4, scopes, label_literals)
            if literal is None:
                continue
            message = tokens[literal]
            quote_width = 3 if message.startswith('"""') else 1
            body = message[quote_width:-quote_width]
            initial = MESSAGE_PREFIX.match(body).end()
            if word := ENGLISH_WORD.match(body, initial):
                offset = matches[literal].start() + quote_width + initial
                violations[offset] = word[0]
    return sorted(violations.items())


def git(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo).decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Check the first English word in Java log messages.")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--commit", help="Check the Java files changed by this commit as stored in that commit.")
    parser.add_argument("files", nargs="*", help="Read these Java files from the working tree. Defaults to the staged Java files.")
    args = parser.parse_args()
    if args.commit and args.files:
        parser.error("choose either --commit or working-tree files")

    if args.files:
        files = args.files
    elif args.commit:
        files = git(args.repo, "diff-tree", "--root", "--no-commit-id", "--diff-merges=first-parent", "-r", "--name-only",
                    "--diff-filter=ACMR", "-z", args.commit, "--", "*.java").split("\0")
    else:
        files = git(args.repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR",
                    "-z", "--", "*.java").split("\0")

    failed = False
    for path in files:
        if not path.endswith(".java"):
            continue
        source = ((args.repo / path).read_text(encoding="utf-8") if args.files
                  else git(args.repo, "show", f"{args.commit or ''}:{path}"))
        for offset, word in lowercase_initials(source):
            line = source.count("\n", 0, offset) + 1
            print(f"{path}:{line}: Start the log message with '{word[0].upper() + word[1:]}' instead of '{word}'.")
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
