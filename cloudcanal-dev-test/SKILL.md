---
name: cloudcanal-dev-test
description: 在 Air 或 Pro 开发和构建 CloudCanal，在 Mini 运行测试并使用真实 Console 验收。现有版本可直接建任务，需要部署时使用独立槽位。也用于 CloudCanal 编码规范、反向合并 dev 和人工提测。
---

# CloudCanal 开发与实库验收

Air、Pro 用于开发和构建。CloudCanal 单测、前端测试、组件测试、JDBC 程序和测试服务都在 Mini 执行。浏览器可以从 Air 或 Pro 访问 Mini Console。新建测试数据库、临时 JDBC 复现和 Docker 数据库优先复用 Mini 已登记实例。需要手工安装时，按[手工部署到 Mini](../datasource-lab/SKILL.md#手工部署到-mini)操作并登记。

只需用现有版本创建或验证任务时，直接选用合适的 Mini Console，在页面创建任务并核对结果。需要加载本轮代码、替换产物或重启服务时，才执行[发布槽位流程](references/mini-release.md)。

测试前把本轮源码、补丁或测试产物放在 Mini 的独立目录。从开发机调用 `python3 scripts/run_mini_test.py --workdir '<Mini 目录>' -- <命令> <参数>`。例如 `python3 scripts/run_mini_test.py --workdir 'datasource-lab/private/releases/<发布 ID>/cloudcanal' -- ./gradlew :ds-oracle:test`。命令行参数和工作目录属于 Mini。回执包含执行主机及测试命令的退出码。组件测试可以通过此入口运行 Mini 上的 `docker exec`。

1. **明确需求和范围。** 记录正常入口、最小可复现条件、可观察结果、涉及仓库和需用的源端、目标端、任务类型。记录各仓库分支、完整 HEAD 和本轮补丁范围。含未提交改动时，从记录的 HEAD 创建独立检出，用 `git diff --binary HEAD` 取得已暂存和未暂存的跟踪文件改动，从中选入本轮补丁。用 `git ls-files --others --exclude-standard` 列出未跟踪文件，另行复制本轮需要的新文件。核对构建目录中的文件清单。保护原工作区和其他执行者的改动。
2. **实现并复核。** 遵循 [编码、提交和人工提测](references/coding-workflow.md)。选择 [Poteto](../pstack/skills/poteto-mode/SKILL.md) 的适用流程前，先读 [cc-setup](skills/cc-setup/SKILL.md#codex-代理)。小改动先复现和修根因。共享逻辑看调用方，设计取舍先核对契约，按可独立验收的任务委派。原版流程见 [索引](references/pstack-index.md)。用户指定 Claude 协作时读 [交接流程](references/claude-collaboration.md)。
3. **构建与测试。** 在开发机使用仅构建的目标，例如 Gradle `assemble` 或 Maven `-Dmaven.test.skip=true package`。用 Mini 测试入口跑本轮单测和引擎组件测试，涉及 JDBC 时验证实际驱动读写。需要发布时按[Mini 槽位发布](references/mini-release.md)独占可用槽位。已登记槽位都被预留时，列出持有者，请用户查看会话并决定。读取槽位私有数据源计划，缺失时按[数据源实验室](../datasource-lab/SKILL.md)补齐已验证的 fixture。
4. **实际验收。** 在已登录的 Mini Console 用真实操作完成验证。数据源和驱动变更使用 [Lab 槽位连接验收](../datasource-lab/SKILL.md#cloudcanal-槽位连接验收)，将每条 Worker 连接结果写进 [Mini CHECK 报告](../datasource-lab/references/check-report.md)。数据任务按 [页面取证](references/browser-job.md) 保存任务 ID、页面和状态，独立读回数据。[Console 自动化](../cloudcanal-console-automation/SKILL.md) 可辅助准备配置和查询证据。Mini Console 页面遇到登录、SSO 或身份复核时，交给用户完成。Mini SSH 提示 Tailscale 复核时，按 [cc-setup 的 Chrome 流程](skills/cc-setup/SKILL.md#填写-minienv)打开复核链接。页面流程未走完时报告已到达的步骤、实际提示和剩余步骤。
5. **交付。** 建任务验收记录 Mini Console 入口、任务 ID、页面结果、目标读回与适用的 CHECK 证据。涉及构建发布时附各仓库 SHA、发布槽位和已加载 JAR 的校验。持续使用本轮槽位时先复核当前任务状态。

## 验收规则与检查

| 验收规则 | 对应检查 |
| --- | --- |
| 所有测试进程运行在 Mini。 | `scripts/run_mini_test.py` 经 SSH 调用主机检查后执行命令，读取测试退出码。 |
| 用现有版本只建任务时直接在 Mini Console 操作。部署新版本时独占槽位。 | 页面建任务记录实际 URL 和任务 ID。部署时用 `scripts/slot_claim.py status` 查询槽位和持有者，申请后记录 `claimId`，测试完成后用 `awaiting-handoff` 保留当前写预留，用户明确要求后释放。所有槽位都被预留时，请用户查看占用会话后选择。启动任务不查预留。改 `slot_claim.py` 的加锁或释放时，按 [verify-slot-claim](skills/verify-slot-claim/SKILL.md) 重跑。 |
| Mini Automation 通过自身登录流程取得会话。页面操作沿用该槽位已登录的浏览器。 | Automation `login --save-cookie` 生成同槽位会话文件。登录或身份复核需交接时保留页面提示。 |
| 需要比较全量和增量时，按同一输入逐笔核对。需要比较版本时，为每个版本保留同样的证据。 | [时间戳读回](references/browser-job.md#全量和增量逐笔核对)使用 `phase-readback` 分别检查正确性和结果是否一致。 |
| Console 端到端结果带本轮任务 ID，组件实测标明实际跑到的读写阶段。 | `browser-job` 核对页面、任务和启动状态。`fresh-check` 核对本轮 CHECK 子任务的完成时间。 |

## 数据链路怎么验

- 从本轮 Console 向导选择真实源、目标和 Worker 集群，检查连接、订阅对象映射和关键参数。保存并启动，打开同一任务详情。用例涉及目标对象自动创建时，核对页面选项并用目标引擎的原生入口确认对象已创建。
- 按用例和实际子任务验证。全量核对预置样本。增量用引擎对应的状态或日志确认本作业读端就绪，再提交带唯一标记的变更。用目标的原生入口读回结果，例如查表、消费消息或读取输出对象。需要比较全量和增量时，使用同一组业务值。验证重启、续跑和配置对照时，分别记录每轮的实际版本和数据。
- 链路支持数据校验且用例要求时，创建本轮独立 CHECK 或从已结束的任务重跑。保存页面结果和本轮任务快照。用 `scripts/check_console_jobs.py fresh-check` 核对完成时间、任务 ID 和新鲜度。以目标原生读回和 CHECK 的实际行数、差异数、漏行数一起判断。
