# 从 Air 或 Pro 发布到 Mini

需要加载代码变更或重启服务时使用发布槽位。只在现有版本创建或验证任务时，直接访问相应 Mini Console，记录任务 ID 和页面结果。

发布前在 Mini 的 `~/datasource-lab` 读取 `MINI-TEST-V1.md` 和 `cloudcanal-service/slots.json`，以登记表中的 `consolePort`、`network`、`project` 选择实际入口。同一槽位串行，不同槽位可并行。用户指定的入口优先。已有槽位都占用时分配下一个独立槽位。例如 01、02 占用且 8113 可用时创建 03，地址为 `http://mini:8113/`。

各槽位共享 Mini 的持久 MySQL 实例和 [Prometheus](http://mini:19090/)。新增槽位时先检查端口、子网和卷名是否空闲，独占预留，准备独立 Compose、Console/RDP schema、私有配置、卷、Worker 和监听端口，并登记 `slots.json`。分支、执行者、槽位、Git SHA、发布时间记在同一发布记录。用 SSH 管理 Mini，通过 `mini` 主机名访问页面。

## 准备产物

新槽位首装分支，或现用产物版本无法确认时，先部署同一发布清单中的整套软件产物，复用槽位的持久卷、schema 和数据源。已有同分支且兼容的基线时，小改可以增量部署。核对现用 JAR 的版本和哈希，按改动及共享依赖确定替换范围。涉及 Console 时，构建用槽位对应的 Maven profile。Mini 03 的 Console 使用 `-Poutput`，Gradle 插件的 `dev` 构建任务是另一套入口。

1. 在 Air 或 Pro 的独立构建目录检出选定提交。用项目实际的 JDK 17 和 Gradle 构建入口。单插件且共享依赖未变时构建对应插件。涉及 Schema 时，先把匹配的依赖发布到本轮隔离的 Maven Local，再构建 CloudCanal。会直接覆盖本机运行目录的安装脚本，只在隔离的构建目录和运行目录中使用。
2. 生成发布清单，包含各仓库完整提交及必要的补丁摘要，每个 JAR 的组件、相对路径、原文件与新文件 SHA-256。传到 Mini 的 `~/datasource-lab/private/releases/<release-id>/`，读回摘要和哈希。
3. 核对槽位登记及独占预留后，在 Mini 运行 `python3 cloudcanal-service/prepare-slot.py <槽号>` 准备已登记的配置，只有需要启动时才带 `--activate`。复用该槽位的 schema 和已登记的数据源。

## 空闲检查、替换与重启

按 [Mini CHECK 报告模板](../../datasource-lab/references/check-report.md) 记录检查结果、目标槽位、计划替换的组件和回退范围。涉及替换、重启或清理的项目经用户确认后，再核对现场并执行。

1. 在 Mini 用 `mkdir ~/datasource-lab/cloudcanal-service/private/.claim-<槽号>` 独占预留。成功后登记执行者、分支、发布 ID 和 UTC 时间，持有至验收或交接结束。预留已存在时选择下一可用槽位。需要发布且现有槽位均占用时执行上面的新增槽位流程。执行中断时先核实持有者和现场，再交接或释放预留。
2. 同一执行者用能看到该 Worker 全部任务的已登录 Console 会话采集所有任务页，按 Worker 筛选。上一轮已知任务未出现在列表时补查该任务。每份 [Worker 取证快照](browser-job.md#发布前的-worker-快照)都带实际请求来源、Worker 和采集时间。用 `python3 scripts/check_console_jobs.py idle --origin "$CONSOLE_ORIGIN" --worker "$WORKER" --not-before "$CLAIM_UTC" page-1.json page-2.json --job previous-job.json` 核对本轮目标槽位、Worker、完整页数和任务状态。按实际页数与补查情况传入文件。遇到正在运行的任务、权限不足或分页缺失时，补齐证据或换空闲槽位。
3. 用实际 Compose 项目及挂载点核对目标文件。备份现用 JAR 和涉及的配置，核对副本哈希。Mini 的 `apply-release-01.py` 只用于 01 首次发布，它要求槽位无任务且目标 schema 为空。其他发布使用 `jar-volume.sh` 按实际挂载和清单校验、备份、替换、还原及读回，或沿用已核实支持该槽位的发布入口。
4. 沿用官方 ARM64 运行镜像和持久卷。停止目标槽位的 Console 和 Sidecar，再替换清单里的 JAR 并重启这两个组件。共享 MySQL、Prometheus 和另一个槽位继续运行。其他服务的 JAR、库和数据源继续使用现有版本与数据。
5. 读回全部替换文件的哈希，核对 Console API、该槽位 Worker `ONLINE` 和 Prometheus 抓取，再核查实际进程或启动日志使用的插件版本。数据源或驱动变更时，按 [Lab 槽位连接验收](../../datasource-lab/SKILL.md#cloudcanal-槽位连接验收) 验证该槽位每条 Worker 连接。JAR、启动或本次连接验收失败时按回退计划处理并复核。需要数据库迁移或回滚时，先核对独立 schema 的实际迁移状态和备份点。
6. 涉及同步、写入或 CHECK 的变更按 [页面取证](browser-job.md) 跑实际任务。保存本轮产物、回退位置、连接或任务页面、原生查询与验收记录到 Mini 私有目录。自测完成后如仍待用户验收，登记待验收项、作业 ID 和持有者，保留槽位供交接。验收或交接结束后，分别记录作业状态、预留状态和环境是否继续保留。只取消占用时只归档预留记录。清理由用户在同一巡检报告中确认。
