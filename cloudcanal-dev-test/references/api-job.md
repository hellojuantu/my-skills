# 默认通过 Console API 验收

用 [Console 自动化](../../cloudcanal-console-automation/SKILL.md) 完成数据源登记、连接测试、建任务、配置、启动和状态查询。

用户要求操作页面时，才走 [页面取证](browser-job.md)。

先确认本轮 Console 来源、同槽位 Automation 会话和 Worker 集群。

陌生的源目标配对，从前端源码、类型、服务定义和动态 WebOp 核对请求。

然后做 dry-run。

不要先打开向导，也不要先抓浏览器请求。

建任务后，读回实际保存的配置、订阅和映射。

异步创建成功后再启动。

`fsmActive=false` 且 `dataTaskState=INIT` 时，按 [任务操作](../../cloudcanal-console-automation/skills/cc-job-operations/SKILL.md) 用 `continue-job` 首次激活 FSM。

有 BUILD_STRUCT 时，要求它是 COMPLETE。

没选结构迁移的新任务也要做这次激活。

首次激活前，`currTaskStatus` 可能是 `UNKNOWN`。

这时普通 `start-job` 会报 current task id empty。

已经激活后又停下的任务，才用普通启动恢复。

查询直到实际工作子任务启动。

在本轮证据目录保存 `create.json` 和启动后的 `query.json`。字段来自实际 API 请求与成功回执，去掉 Cookie、凭据和不需要的请求体。

`create.json` 保留 `requestUrl`、`method`、`httpStatus`、`code` 和 API 返回的 `dataJobId`。例如：

```json
{"requestUrl":"http://<本轮主机>:<端口>/cloudcanal/console/api/v1/inner/datajob/create","method":"POST","httpStatus":200,"code":"1","dataJobId":123}
```

`query.json` 保留实际 `queryjob` 的 `requestUrl`，以及 `data` 下的 `dataJobId`、`fsmActive` 和 `dataTasks`。子任务保留 `dataTaskId`、`dataTaskType`、`dataTaskStatus`，需要 CHECK 新鲜度检查时另保留完成时间与计数。

```sh
python3 scripts/check_console_jobs.py api-job "$directory" "$directory/query.json"
```

这条检查只核对同一来源、创建 ID 和实际启动状态。

任务启动不代表数据正确。

全量要读回预置样本。

增量先确认该作业的读端就绪，再写入带唯一标记的变更，并用目标自己的入口读回。

二进制核对实际字节、长度和哈希。

全量和增量按用例分开记。

后续使用同一组通用检查：

- [停止本轮新建增量验收任务](browser-job.md#新建增量验收任务收尾)，保存 `stopped-test-job` 回执。
- [全量与增量逐笔核对](browser-job.md#全量和增量逐笔核对)，保存原生读回，按需要运行 `phase-readback`。
- [发布前 Worker 快照](browser-job.md#发布前的-worker-快照)，通过 API 采集完整分页与补查回执，再运行 `idle`。
- CHECK 按任务 ID 运行 `fresh-check`，核对这轮完成时间、检查行数、差异数和漏行数。

交付写实际入口、任务与子任务 ID、API 状态、目标读回、停止后的状态及未完成项。默认流程不要求页面截图。
