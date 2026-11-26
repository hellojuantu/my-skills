# Codex 与 Claude 协作

这套方法也可以用在别的代码库。CloudCanal 的 Mini 部署和数据源配置从技能入口查。发给 Claude 的内容只包括完成评审或修复需要的技术背景。

## 从复现到交付

1. Codex 先复现。
   记下版本、实际入口、预期结果和实际结果。
   尽量找到最小反例。
   分开看是存储、显示、校验还是配置的问题。
   涉及源端或目标端时，分别追全量、CDC、校验，以及实际启用的 typed 和非 typed 路径。
2. 把明确的工作交给 Claude。
   默认给用户一段可转发的英文。
   先写症状和能重复的证据，再写希望它核实的代码路径、验收条件、要保留的现有行为，以及先不做的事。
   用户要求先分析时，写明在查清受影响入口之前不要改代码。
3. 写明这一轮谁改代码。
   Claude 改时，Codex 做独立 review，读用户指定的会话，准备测试和环境。
   用户让 Codex 修时，再接手代码。
   同一个文件交给一方改，这样补丁和测试结果对得上。
4. 逐项核实 Claude 的回复。
   把初步推断、源码确认、仓库改动和测试通过分开记。
   回到调用点，确认组件测试盖住了实际入口。
   沿着共享的 reader、writer、序列化和默认配置看相邻路径。
   确认回归用例在旧行为下会失败，并且同时覆盖应该相等和应该不等的输入。
   读对话和看补丁都是 review。
   转不转发仍由用户决定。
5. 按用户指定的完成条件往下做。
   要交付的修复都准备好了，才同步并开始正式集成复测。
   Claude 暂停、额度用完，或路径还没确认时，向用户说明已经证实的结果和卡住的那一步，同时继续能独立做的验证。
   恢复后先看补丁状态，避免把做过的验证再做一遍。
6. Codex 收尾。
   针对实际补丁重跑回归。
   需要实库时，先确认目标端读回，再看校验结果，比较修复前后。
   回报补丁和测试状态、用例或任务 ID、剩下的差异、确切的阻塞。
   只有用户授权，才改原代码、提交或推送。

## 直接连接用户的 Claude 会话

用户已经授权直接协作，并且有可用的终端会话时，先核对目标是他指定的那个 Claude 会话。

看当前任务、Claude 是否空闲、输入框是否空白。

正忙或已有草稿时，留下现场，继续能独立做的工作。

连接方式由用户的环境决定，例如已经存在的 tmux 会话。

交接、追问和反馈都用英文，用用户的措辞。

只发送核实、修改和测试需要的内容。

部署细节、主机、凭据、其他会话和本技能的内容留在本地。

发出后读回最近的消息和状态，确认送到了并且对方在继续。

状态不明时先读回，避免重复发送。

回复只给 Codex 收集证据。

接受范围外的修改、提交和推送，仍由用户决定。

## 给 Claude 的英文交接模板

> Please verify the causal path for each reproduced issue, then make the smallest fix within the agreed scope. For each issue, here is the entry point, the observed result, and the expected result.
>
> [Insert the failing case, a passing control, and the relevant code paths.]
>
> Trace the actual feature entry points and confirm the behavior of any shared paths affected by your change. Add a regression test for the failing case and include the test output. Call out any behavior changes, existing failures, or coverage that still needs integration testing. Keep [out-of-scope item] out of this patch. Let me know which fixes are ready for independent review and retesting.

复杂改动可以分两次交接。先请 Claude 只确认路径和比较方案。等用户确认语义之后再改。例子用本轮的证据写。不要把某一条业务链路的临时要求写成其他仓库的通用规则。
