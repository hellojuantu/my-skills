---
name: juantu-mode
description: "Use Juantu's working preferences when asked for /juantu-mode, juantu-mode, or to work in Juantu's style. Covers how to answer, when to confirm a plan, and how to write code a person can read. For Codex and Cursor."
disable-model-invocation: true
---

# Juantu mode

Codex 和 Cursor 读同一份。用户要 `/juantu-mode`，或要按 Juantu 的习惯做时，按这里做。

## 定范围和方案

先读，不改。把范围写清楚。要改多个仓库，或要改已经在用的行为时，先给方案，等用户同意。

方案用白话。表格写现在、改完、怎么验。关键代码贴在对话里，改前几行，改后几行。

用户要 [poteto-mode](../pstack/skills/poteto-mode/SKILL.md) 时，走那个流程。

按要做的事打开对应技能。

- 定边界，读 [architect](../pstack/skills/architect/SKILL.md)。
- 要几套方案，读 [arena](../pstack/skills/arena/SKILL.md)。
- 要分头看，读 [swarm](../pstack/skills/swarm/SKILL.md)。
- 要查旧调用，读 [blast-radius](../pstack/skills/blast-radius/SKILL.md)。

## 讲 bug

回答用户刚才问的那一句。用户换了问题，就答新的。

先写结果。你跑过命令，就把命令和输出写上。结论来自读代码，就写明是读代码。

先写用户能看到的现象。

再写走错的那一步，旁边标当时的值，代码贴在对话里。

用过 [how](../pstack/skills/how/SKILL.md) 或 [why](../pstack/skills/why/SKILL.md) 之后，按这几句重写。

不要把架构说明原样交出来。

## 写代码

让下一个人按顺序读懂。能先判断的先判断。条件不成立就返回，再取值，再调用。

互不相关的退出写成单独的 `if`。先判空，先确认类型，再读字段。条件写短。

相邻的提前返回之间空一行。正常返回和上一个判断之间也空一行。

一个条件里又校验，又调用，又决定返回值时，拆成 `if` 和正常返回。

同一类错误被纠正两次之后，按 [correct](../pstack/skills/correct/SKILL.md) 改实现。

只属于一个项目的规则写在那个项目里。

这几条是习惯。

不要为某一段代码再写一个专用检查脚本。

检查要在写错的代码或交出去的文件上失败。

只核对技能原文里某几句话还在的脚本，删掉。

## 实现和分工

先找仓库里最接近的写法。能用就用。只改这一轮的问题。

## 验收和交付

按项目要求跑测试。再从用户平时的入口做一次，看他能看到的结果。写过数据，就从目标端读回来。

交付先写结果。再写跑过的测试、入口和看到的现象。有任务就写 ID。卡住时写停在哪一步、提示是什么、还没做的步骤。
