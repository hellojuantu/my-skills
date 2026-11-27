---
name: cloudcanal-dev-test
description: 在 Air 或 Pro 开发和构建 CloudCanal，在 Mini 运行测试并使用真实 Console 验收。现有版本可直接建任务，需要部署时使用独立槽位。也用于 CloudCanal 编码规范、反向合并 dev 和人工提测。
---

# CloudCanal 开发与实库验收

Air 和 Pro 用来写代码、构建。单测、前端测试、组件测试、JDBC 程序和测试服务都在 Mini 上跑。

默认用 [Console API 自动化](../cloudcanal-console-automation/SKILL.md) 创建、配置、运行和验收测试。

用户要求看页面时，才打开浏览器。

新的测试库优先用 Mini 上已经登记的实例。

用户没有明确要求时，不要创建备份。

用户要求备份时，按 [备份](references/backups.md) 做。

没有合适实例时，按 [手工部署到 Mini](../datasource-lab/SKILL.md#手工部署到-mini) 安装并登记。

只用现有版本建任务或查看任务时，直接调用对应 Mini Console 的 API。

要加载这轮改过的代码、换 JAR 或重启服务时，才走 [发布槽位](references/mini-release.md)。

测试前把这轮源码、补丁或产物放到 Mini 的单独目录。从开发机运行：

```sh
python3 scripts/run_mini_test.py --workdir '<Mini 目录>' -- <命令> <参数>
```

工作目录和命令都在 Mini 上执行。回执里有执行主机和退出码。组件测试也可以经这个入口在 Mini 上跑 `docker exec`。

## 一轮改动怎么做

1. 先写清范围。
   只在有改动的仓库创建或切换任务分支。
   没改的仓库留在原来的分支。
   构建依赖时，用指定 SHA 的独立检出。
   不要把没改的仓库切到同名分支。
   记下正常入口、最小复现和能观察到的结果。
   记下涉及的仓库、源端、目标端和任务类型。
   记下每个仓库的分支、完整 HEAD，以及这轮补丁包含哪些文件。
   工作区里还有别人的改动时，从记下的 HEAD 另做一个检出。
   用 `git diff --binary HEAD` 取出这轮要带上的改动。
   用 `git ls-files --others --exclude-standard` 找出要另拷的新文件。
2. 再改代码。
   编码、提交和提测按 [编码约定](references/coding-workflow.md)。
   要用 Poteto 流程时，先读 [Codex 代理](skills/cc-setup/SKILL.md#codex-代理)。
   小改动先复现，再改出错的那一步。
   改共享逻辑时看调用方。
   原版流程目录在 [索引](references/pstack-index.md)。
   用户指定和 Claude 一起做时，读 [交接](references/claude-collaboration.md)。
3. 然后构建和测试。
   开发机只做构建，例如 Gradle `assemble`，或 Maven `-Dmaven.test.skip=true package`。
   单测和引擎组件测试用上面的 Mini 入口。
   涉及 JDBC 时，用真实驱动做一次读写。
   需要发布时，按 [槽位发布](references/mini-release.md) 独占一个空槽位。
   槽位都被占时，列出持有者，等用户看过会话再决定。
   槽位上缺测试库时，按 [数据源实验室](../datasource-lab/SKILL.md) 补。
4. 最后通过 Mini Console API 自动化验收。
   数据源或驱动有改动时，做 [槽位连接验收](../datasource-lab/SKILL.md#cloudcanal-槽位连接验收)。
   把每条 Worker 连接写进 [Mini CHECK 报告](../datasource-lab/references/check-report.md)。
   数据任务按 [API 取证](references/api-job.md) 保存请求来源、任务 ID 和状态，再从目标端把数据读回来。
   准备配置和查询用 [Console 自动化](../cloudcanal-console-automation/SKILL.md)。
   使用同槽位的 Automation 登录会话；API 确实返回需要人工完成的身份复核时，报告原始提示。
   SSH 要求 Tailscale 复核时，按 [Mini SSH 身份复核](skills/cc-setup/SKILL.md#mini-ssh-身份复核) 打开链接。
   API 操作失败时，记录接口、任务 ID、原始错误和未完成步骤。用户要求页面操作时，按 [页面取证](references/browser-job.md) 保存页面证据。
5. 收尾。
   按 [新建增量验收任务收尾](references/browser-job.md#新建增量验收任务收尾) 停掉这轮为了验收新建的增量任务。
   交付里写 Mini Console 入口、任务 ID、API 结果和目标读回。
   发布过时，附上各仓库 SHA、槽位，以及已加载 JAR 的校验。

## 验收规则与检查

测试进程都在 Mini 上。`scripts/run_mini_test.py` 先经 SSH 确认主机，再执行命令，并读回退出码。

现有版本上建任务时，直接用 Mini Console。记下实际 URL 和任务 ID。

部署新版本时独占槽位。

用 `scripts/slot_claim.py status` 看槽位和持有者。

申请后记下 `claimId`。

测完后用 `awaiting-handoff` 留着这次写预留。

用户明确要求再释放。

槽位都被占时，把占用会话列给用户选。

启动任务不查预留。

改了 `slot_claim.py` 的加锁或释放时，按 [verify-slot-claim](skills/verify-slot-claim/SKILL.md) 重跑。

Mini Automation 用自己的 `login --save-cookie` 拿到这个槽位的会话。

用户明确要求页面操作时，用这个槽位已经登录的浏览器。

登录或身份复核要交接时，把页面提示留下来。

要比较全量和增量时，用同一份输入逐笔对。

要比较版本时，每个版本留同样的证据。

时间戳读回见 [全量和增量逐笔核对](references/browser-job.md#全量和增量逐笔核对)，用 `phase-readback` 分别看值对不对、两阶段是否一致。

Console 的端到端结果要带这轮任务 ID。

组件实测要写明实际跑到的读写阶段。

默认用 `api-job` 核对 API 创建、任务和启动状态；用户要求页面时才用 `browser-job` 核对截图与页面来源。

`fresh-check` 核对这轮 CHECK 子任务的完成时间。

增量验收收尾时，停掉这轮新建并启动的任务。

用户要求继续跑时，记下状态。

`stopped-test-job` 核对停止后的同一份回执，确认 `fsmActive=false`，增量子任务是 `STOP`。

## 数据链路怎么验

通过 Console API 查询并选择真实的源、目标和 Worker 集群。

看连接、订阅对象和关键参数。

保存后用 API 读回配置与映射；启动后查询同一个任务及其子任务状态。

用例要求自动建目标对象时，核对 API 保存的选项，再用目标引擎自己的入口确认对象已经建出来。

全量核对事先放好的样本。

增量先用引擎的状态或日志确认这个作业的读端就绪，再写入一条带唯一标记的变更，然后用目标自己的入口读回来。

比较全量和增量时用同一组业务值。

验证重启、续跑或配置对照时，每一轮分开写版本和数据。

链路支持校验而且用例要求时，建一轮独立的 CHECK，或从已结束的任务重跑。

保存 API 结果和这轮任务快照。

用 `scripts/check_console_jobs.py fresh-check` 核对完成时间、任务 ID 和是不是这轮新跑的。

判断时同时看目标读回，以及 CHECK 的行数、差异数和漏行数。
