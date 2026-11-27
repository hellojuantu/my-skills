# 从 Air 或 Pro 发布到 Mini

要加载代码变更或重启服务时，用发布槽位。只在现有版本上创建或验证任务时，直接用对应 Mini Console 的 API 自动化。记下任务 ID 和 API 结果；页面操作只在用户明确要求时执行。

发布前在 Mini 的 `~/datasource-lab` 读 `MINI-TEST-V1.md` 和 `cloudcanal-service/slots.json`。

按登记表里的 `consolePort`、`network`、`project` 选实际入口。

同一槽位串行。

不同槽位可以并行。

用户指定的入口优先。

已登记槽位都被预留时，按 [释放与交接](#释放与交接) 列出占用会话，等用户看过再决定。

用户已经指定新槽位时，按指定入口准备。

按槽位登记和实际 Compose 核对元数据库和 Prometheus。有的槽位用共享服务，有的用独立服务。

新增槽位时，先检查端口、子网和卷名是否空闲。

然后独占预留。

准备独立 Compose、Console 和 RDP schema、私有配置、卷、Worker 和监听端口。

登记到 `slots.json`。

分支、执行者、槽位、Git SHA 和发布时间记在同一条发布记录里。

Mini 的访问主机名从 `mini.env` 读。

## 准备产物

新槽位第一次装这个分支，或现用产物版本无法确认时，先部署同一发布清单里的整套产物。

复用槽位的持久卷、schema 和数据源。

已有同分支且兼容的基线时，小改可以增量部署。

核对现用 JAR 的版本和哈希。

按改动和共享依赖确定替换范围。

涉及 Console 时，构建用槽位对应的 Maven profile。

Mini 03 的 Console 使用 `-Poutput`。

Gradle 插件的 `dev` 构建任务是另一套入口。

1. 在 Air 或 Pro 的独立构建目录检出选定提交。
   用项目实际的 JDK 17 和 Gradle 入口构建。
   只改一个插件且共享依赖没变时，构建对应插件。
   涉及 Schema 时，先把匹配的依赖发到本轮隔离的 Maven Local，再构建 CloudCanal。
   会直接覆盖本机运行目录的安装脚本，只在隔离的构建目录和运行目录里用。
2. 生成发布清单。
   包含各仓库完整提交和必要的补丁摘要，以及每个 JAR 的组件、相对路径、原文件和新文件 SHA-256。
   增量发布同时记录所用的基线发布。
   传到 Mini 的 `~/datasource-lab/private/releases/<release-id>/`。
   读回摘要和哈希。
3. 新槽位或需要重新生成槽位配置时，核对登记和独占预留。
   在 Mini 运行 `python3 cloudcanal-service/prepare-slot.py <槽号>`。
   需要启动时才加 `--activate`。
   已有兼容基线的 JAR 更新，直接复用该槽位的配置、schema 和数据源。

## 空闲检查、替换与重启

按 [Mini CHECK 报告模板](../../datasource-lab/references/check-report.md) 记录检查结果、目标槽位、计划替换的组件和回退范围。

已授权的 Mini 发布，在取得 `write` 预留并核对 Worker 空闲后直接执行。

用户没有明确要求时，不要创建备份。

用户要求备份时，按 [备份](backups.md) 做。

环境清理按巡检报告确认。

1. 在 Air 或 Pro 的技能目录运行 `python3 scripts/slot_claim.py status`。
   同一会话继续同一分支时，沿用已经持有的目标槽位 `write` 预留。
   第一次占位运行 `python3 scripts/slot_claim.py acquire 03 --access write --machine Pro --agent Codex --run-id "$RELEASE_ID" --branch "$BRANCH"`。
   现有版本上建任务或验证，又需要专门留住槽位时，申请 `--access read`。
   机器和执行工具用实际值。
   用 `--session-title`、`--session-id` 和 `--session-url` 记录能核实的会话。
   链接填实际能打开的地址。
   Codex 有 `CODEX_THREAD_ID` 时，自动记录会话 ID。
   用户明确要求新增槽位时，加 `--new-slot`。
   Mini 把归属写到 `private/.claim-<槽号>/owner.json`。
   保存回执里的 `claimId` 和 `claimedAt`。
   用 `claimId` 关联每轮发布记录。
   预留的 `runId` 记录初次申请。
   每轮产物用自己的发布 ID。
   预留留到用户明确要求释放。
2. 每轮记录 `IDLE_CHECK_UTC`。
   取持有预留后、本轮空闲检查开始的 UTC 时间。
   同一执行者用能看到该 Worker 全部任务的已登录 Console 会话，按 Worker 筛选，采集所有任务页。
   上一轮已知任务没出现在列表里时，补查该任务。
   每份 [Worker 取证快照](browser-job.md#发布前的-worker-快照) 都带实际请求来源、Worker 和采集时间。
   用 `python3 scripts/check_console_jobs.py idle --origin "$CONSOLE_ORIGIN" --worker "$WORKER" --not-before "$IDLE_CHECK_UTC" page-1.json page-2.json --job previous-job.json` 核对本轮目标槽位、Worker、完整页数和任务状态。
   按实际页数和补查传入文件。
   遇到正在运行的任务、权限不足或分页缺失时，补齐证据，或换一个空闲槽位。
3. 用实际 Compose 项目和挂载点核对目标文件。
   可重建的 JAR 使用原发布清单和已有产物作为恢复来源，不额外备份。
   用户要求备份时，按 [备份](backups.md) 创建并核对清单与哈希。
   会迁移元数据库时，启动前核对迁移范围和数据库回退点。
   Mini 的 `apply-release-01.py` 只用于 01 首次发布。
   它要求槽位无任务，且目标 schema 为空。
   其他发布用 `jar-volume.sh`，按实际挂载和清单校验、替换、还原和读回。
   用户没有要求备份时，跳过自动备份。
   用户要求备份时，用 `backup.py check-path` 核对目标。
   容器里已有的暂存备份只移动。
   不要复制，也不要追加。
   也可以沿用已经核实支持该槽位的发布入口。
4. 发布入口在停服务前运行 `python3 scripts/slot_claim.py update 03 --claim-id "$CLAIM_ID" --phase deploying`。
   成功后再继续。
   沿用官方 ARM64 运行镜像和持久卷。
   按 Compose 挂载和进程加载范围，停止使用待换 JAR 的服务。
   替换后重启这些服务。
   全量发布通常同时涉及 Console 和 Sidecar。
5. 读回全部替换文件的哈希。
   核对 Console API、该槽位 Worker `ONLINE` 和 Prometheus 抓取。
   再看实际进程或启动日志使用的插件版本。
   数据源或驱动变更时，按 [Lab 槽位连接验收](../../datasource-lab/SKILL.md#cloudcanal-槽位连接验收) 验证本轮涉及的 Worker 连接。
   JAR、启动或这次连接验收失败时，按回退计划处理并复核。
   涉及元数据库迁移时，核对本轮实际迁移结果。
6. 涉及同步、写入或 CHECK 的变更，按 [API 取证](api-job.md) 跑实际任务。
   用户要求看页面时，才补页面证据。
   本轮产物、连接或任务 API 回执、原生查询和验收记录存到 Mini 私有目录。
   已经有备份时，只记下 `/tmp/codex-backup` 里的位置。
   不要为了交付再追加一份备份。
   按 [释放与交接](#释放与交接) 记录作业状态、预留状态，以及环境是否继续保留。

## 释放与交接

测试完成时，保留本轮 `write` 预留。

运行 `python3 scripts/slot_claim.py update 03 --claim-id "$CLAIM_ID" --phase awaiting-handoff --job-id 123 --note '待验事项'`。

填写实际任务 ID 和验收结果。

多笔任务重复传 `--job-id`。

没有任务时省略。

交付里列出槽位、任务和待验事项。

`status` 返回 `allRegisteredClaimed: true` 时，按同一份快照列出每个槽位。

列出端口、机器、run ID、分支、会话标题、会话 ID 和 `claimId`。

能打开的会话链接附在对应行。

没有链接时，用标题或 ID 定位。

旧记录缺少的字段标为「未记录」。

请用户打开相应对话，决定保留、释放哪一条，或另行新建槽位。

用户决定前，保留所有预留。

用户明确要求释放某个槽位时，核对该条预留和当前 `claimId`。

执行 `python3 scripts/slot_claim.py release 03 --claim-id "$CLAIM_ID" --user-confirmed`。

接手遗留预留时，先向用户核实原会话已结束，并确认现场没有进行中的发布或回退。

Mini 在槽位独占锁内比较 ID。

匹配的预留归档到 `private/claim-history/`。

ID 已经变化时，重新展示新持有者，由用户决定。

任务、数据源、JAR 和数据保留。

释放后如果还要部署，重新申请，并采集本轮 Worker 空闲证据。

在现有版本上建任务、启动、继续或停止任务时，直接使用 Mini Console。目标槽位正在替换组件时，用其他可用 Console，或等重启结束。
