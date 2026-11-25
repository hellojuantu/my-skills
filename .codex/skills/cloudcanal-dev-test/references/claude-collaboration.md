# Codex 与 Claude 协作

这套协作方法可用于其他代码库。CloudCanal 的 Mini 部署和数据源配置从技能入口查找。对话中发给 Claude 的内容只包括完成评审或修复所需的技术背景。

## 从复现到交付

1. **Codex 先复现。** 记录版本、实际入口、预期结果和实际结果。尽量找到最小反例，并区分存储、显示、校验和配置问题。涉及源端或目标端时，分别追踪全量、CDC、校验，以及 typed／非 typed 等实际启用的路径。
2. **把明确的工作交给 Claude。** 默认给用户一段可转发的英文消息，由用户在 Claude 会话里发。先写症状和可重复证据，再写希望它核实的代码路径、验收条件、该保留的现有行为及暂缓项。用户要求先分析时，明确让 Claude 在查清受影响入口前暂停修改。
3. **明确这一轮谁改代码。** Claude 实施时，Codex 做独立 review、读取用户指定会话、准备测试和环境。用户让 Codex 修复时再接手代码改动。同一个文件的修改交给一方，以便把补丁和测试结果对应起来。
4. **逐项核实 Claude 的回复。** 把初步推断、源码确认、仓库改动和测试通过分开记录。回到调用点确认组件测试确实覆盖实际入口。沿着共享 reader、writer、序列化和默认配置检查相邻路径。确认回归用例在旧行为下会失败，并覆盖应该相等和应该不等两类输入。读取对话和看补丁都属于 review，用户转发决定仍由用户掌握。
5. **按用户指定的完成条件推进。** 只有要交付的修复都准备好，才同步并开始正式集成复测。Claude 暂停、额度限制或路径尚未确认时，向用户说明已证实的结果和卡住的具体步骤，同时继续独立的验证工作。恢复后从检查补丁状态开始，避免重复已完成的验证。
6. **Codex 收尾。** 针对实际补丁重跑回归。需要实库时，先确认目标实际读回，再看校验结果，比较修复前后。回报补丁及测试状态、用例／任务 ID、剩余差异、确切阻塞。只有用户授权才修改原代码、提交或推送。

## 直接连接用户的 Claude 会话

如果用户已授权直接协作，并有可用的终端会话连接，先核对目标是用户指定的 Claude 会话，核对当前任务上下文、Claude 是否空闲以及输入框是否空白。忙碌或已有草稿时保留现场，继续可独立完成的工作。连接方式由用户环境决定，例如已存在的 tmux 会话。交接、追问和反馈都用英文，沿用用户的措辞和直接委托口吻。只发送核实问题、修改和测试所需的内容；部署细节、主机信息、凭据、其他会话及本技能的内容留在本地。发送后读回最近的消息和状态，确认投递与接续。状态不明时先读回，避免重复发送。回复仅供 Codex 收集证据，接受范围外修改、提交、推送等决定仍由用户掌握。

## 给 Claude 的英文交接模板

> Please verify the causal path for each reproduced issue, then make the smallest fix within the agreed scope. For each issue, here is the entry point, the observed result, and the expected result.
>
> [Insert the failing case, a passing control, and the relevant code paths.]
>
> Trace the actual feature entry points and confirm the behavior of any shared paths affected by your change. Add a regression test for the failing case and include the test output. Call out any behavior changes, existing failures, or coverage that still needs integration testing. Keep [out-of-scope item] out of this patch. Let me know which fixes are ready for independent review and retesting.

复杂改动可分两次交接。先请 Claude 只做路径确认和方案比较，等用户确认语义后再实施。例子以本轮证据生成，避免把某条业务链路的临时要求当成其他仓库的通用规则。
