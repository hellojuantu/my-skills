#!/usr/bin/env python3
"""Fail when juantu-mode no longer requires the short bug explanation."""

import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"

REQUIRED = (
    "先答用户这一问",
    "丢掉上一句的框架",
    "对照表",
    "贴不超过 8 行代码",
    "登录被跳过后实际发生的事",
    "第一句是命令或实测状态",
    "不把 how 的架构说明原样贴出",
)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else SKILL
    text = path.read_text(encoding="utf-8")
    missing = [line for line in REQUIRED if line not in text]
    if missing:
        print(f"{path}: 讲 bug 缺少这些句子，下一次会写成听不懂的长文：")
        for line in missing:
            print(f"  - {line}")
        return 1
    print(f"{path}: 讲 bug 的固定答法还在")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
