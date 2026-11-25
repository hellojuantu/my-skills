---
name: juantu-mode
description: Use Juantu's working preferences when explicitly asked for /juantu-mode, $juantu-mode, or to work in Juantu's style.
---

# Juantu mode

## 定范围和方案

先弄清用户要什么、会改到哪里、用什么结果判断完成。接手已有任务时，先核对已完成的步骤，再从未完成的地方继续。

用户点名用 [pstack:poteto-mode](../pstack/skills/poteto-mode/SKILL.md) 做任务时，按它为当前任务选流程。使用各子技能时，遵守本轮授权、下文的方案确认规则和当前项目的验收要求。

要查现在怎么运行、代码该放哪里时，按 [pstack:how](../pstack/skills/how/SKILL.md) 查实际入口和调用过程。要查当初为什么这样设计、一次改动为什么引入时，按 [pstack:why](../pstack/skills/why/SKILL.md) 查提交和讨论，区分记录与推断。两者都涉及时分别查证，再用白话讲清。

可以先只读排查。用户要求先看方案、预计要修改多个仓库，或会改变既有兼容行为时，先给方案，等用户明确同意再动手。执行中才发现涉及这些情况，也先等确认再扩大改动。已授权、兼容的单仓库小修可以直接完成。

需要定接口、模块边界或比较不同改法时，按 [pstack:architect](../pstack/skills/architect/SKILL.md) 梳理方案。需要对同一个问题独立做几套方案时，用 [pstack:arena](../pstack/skills/arena/SKILL.md)，按同一组标准和验证结果比较候选。

先用白话讲清问题和用户会看到的变化。用表格对比「现在」「改完后预期」「怎么验」。关键代码贴改前和改后各几行。标明现状是实测结果还是读代码得出的判断。

## 实现和分工

先找最接近的现有实现，沿用适用的通用代码，改动以解决本轮问题为限。可以独立完成的工作按角色并行，同一处改动由一人负责。用户要求多位代理分别查看不同部分时，用 [pstack:swarm](../pstack/skills/swarm/SKILL.md) 分工并汇总。

遇到反复纠正的问题，按 [pstack:correct](../pstack/skills/correct/SKILL.md) 处理。先看能否从实现上消掉容易出错的写法。适合自动检查的规则放在所属项目，用以前的错误验证检查确实能拦住。

## 验收和交付

需要检查共享代码或兼容改动会影响哪里时，按 [pstack:blast-radius](../pstack/skills/blast-radius/SKILL.md) 查受影响的调用方和旧用法，并实际跑能验证关键风险的用例。

1. 按项目规则跑相关单元、组件或集成测试。
2. 在本次要验的版本和环境，从用户平时使用的入口完成相关操作，例如创建、修改、连接或恢复。操作后核对用户能看到的结果。涉及任务或记录时，回看同一对象的状态或内容。涉及数据写入或同步时，从目标端读回核对。涉及兼容性时，复跑受影响的旧用法。
3. 交付先说结果，再给实际跑过的测试、使用的入口和观察到的结果。适用时附上环境、版本和任务或记录 ID。受阻时，写明卡在哪一步、看到的提示和还没完成的步骤。
