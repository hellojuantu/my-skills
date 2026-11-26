# 采集 Console 页面建任务证据

用现有版本创建任务时，直接打开对应的 Mini Console。

需要部署时，按 [发布流程](mini-release.md) 进入本轮独占的槽位。

进向导之前看浏览器地址栏的协议、主机和端口。

沿用这个入口已经登录的会话。

交接时记下实际页面。

停在登录页时，写明入口和还没完成的登录步骤。

Console 遇到登录页、SSO 或身份复核时，交给用户。

Mini 主账号以该槽位私有文件 `~/datasource-lab/cloudcanal-service/private/slot-<NN>/console.env` 的 `USER_EMAIL` 为准。

不要套用 Air 或默认账号。

页面提示 `Account not exist` 表示账号查找失败。

先对照所填账号和 `USER_EMAIL`。

在已有授权范围内，只读核对该槽位 RDP schema 里配置的账号是否存在且已启用。

保留原始提示。

不要重试密码。

密码只在私密登录环节使用。

要通过 Automation 操作时，用 `login --base-url "$CONSOLE_ORIGIN" --save-cookie "$SESSION_FILE"` 创建同槽位会话。

后面的命令传 `--cookie-file "$SESSION_FILE"`。

DevTools 用来留页面验收证据。

证据里保留请求来源、结果码和任务 ID。

在本轮单独的目录里保存页面证据。

先用浏览器按验收用例填向导。

记下源端、目标端、订阅对象、关键设置，以及对应页面截图。

Playwright，包括通过 CDP 连接已有 Chrome，可以在最后一次提交前用下面的代码。

用本轮实际控件的点击替换 `clickSubmit`。

`page` 是正在填向导的页面。

`directory` 是已经建好的证据目录。

```js
const fs = require('node:fs/promises');
const path = require('node:path');
const save = (file, data) => fs.writeFile(path.join(directory, file), JSON.stringify(data));
const pageUrl = page.url();
const [response] = await Promise.all([
  page.waitForResponse(r =>
    r.request().method() === 'POST' &&
    new URL(r.url()).pathname === '/cloudcanal/console/api/v1/inner/datajob/create'
  ),
  clickSubmit()
]);
const { code, data: dataJobId } = await response.json();
await save('create.json', {
  pageUrl, requestUrl: response.url(), method: response.request().method(),
  httpStatus: response.status(), code, dataJobId: Number(dataJobId)
});
```

在页面启动任务。

已经配置自动启动时，观察它启动。

从列表打开刚创建的任务。

确认详情与预期任务名、状态一致，然后采集页面 URL 和截图。

使用原生 CDP 或浏览器开发者工具时，从同一页面请求和详情页读取相同字段即可。

证据只留成功响应码和 ID 等所列字段。

保存时去掉 Cookie、请求体和连接凭据。

```js
await save('detail.json', { pageUrl: page.url() });
await page.screenshot({ path: path.join(directory, 'detail.png') });
```

CUA 的截图是 JPEG，按实际格式保存为 `detail.jpg`。每轮证据目录留一张详情截图。

任务启动后刷新详情页。

采集实际 `queryjob` 请求的 URL 和成功响应。

把最少必要字段保存到 `query.json`。

用已登录 CLI 补查时，同样记下实际请求 URL。

下面的例子沿用上面的 Playwright 会话。

```js
const [query] = await Promise.all([
  page.waitForResponse(r => r.request().method() === 'POST' &&
    new URL(r.url()).pathname === '/cloudcanal/console/api/v1/inner/datajob/queryjob'),
  page.reload()
]);
const { code: queryCode, data: job } = await query.json();
if (!query.ok() || String(queryCode) !== '1') throw new Error('queryjob failed');
const dataTasks = job.dataTasks.map(({dataTaskId, dataTaskType, dataTaskStatus}) =>
  ({dataTaskId, dataTaskType, dataTaskStatus}));
await save('query.json', {requestUrl: query.url(), data: {dataJobId: job.dataJobId, dataTasks}});
```

在技能目录运行：

```sh
python3 scripts/check_console_jobs.py browser-job "$directory" "$directory/query.json"
```

这条命令核对向导创建、详情和查询的 Console 来源。

它验证截图格式、任务 ID、子任务 ID 和启动状态。

再按用例逐项看截图里的设置、全量与增量状态、目标原生读回，以及独立 CHECK 的计数和明细。

失败时，报告已经到达的页面、原始提示和缺少的证据。

## 新建增量验收任务收尾

目标读回完成，并且本轮最后一次增量验证也完成之后，停止本轮为了验收新建并启动的增量任务。验收因失败结束时，先保存失败证据，再停止。用户要求继续运行时，记下任务 ID 和当前状态。

停任务时用创建回执里的 Console 入口和任务 ID。

在同一详情页点击停止，或使用 [cc-job-operations 的 `stop-job`](../../cloudcanal-console-automation/skills/cc-job-operations/SKILL.md#lifecycle)。

停止后刷新同一任务。

查询直到 `fsmActive=false`，并且每个 `INCREMENT` 子任务为 `STOP`。

把最后一次停止后的成功 `queryjob` 回执单独保存为 `stopped-query.json`。

保留 `requestUrl`。

`data` 下保留 `dataJobId`、`fsmActive`、`dataTasks`。

子任务保留 `dataTaskId`、`dataTaskType`、`dataTaskStatus`。

在技能目录核对回执。

交付里记录作业 ID、增量子任务 ID 和状态。

```sh
python3 scripts/check_console_jobs.py stopped-test-job --origin "$CONSOLE_ORIGIN" \
  --job-id "$JOB_ID" "$directory/stopped-query.json"
```

查询或停止受阻时，记下任务 ID、最后见到的状态和提示。部署过本轮产物时，槽位预留按 [发布流程](mini-release.md) 交接。

## 已有任务和连接测试

换包后恢复已有任务时，用同一任务详情页和 `queryjob` 核对任务 ID、子任务 ID 和状态。

涉及增量续跑时，记下停止前的持久化位点，以及恢复后的位点或读端状态。

按本轮用例核对目标原生读回。

发布清单记录实际加载的 JAR。

只有创建新任务时才采集创建请求。

只改连接或驱动时，保存真实 Console 的数据源 ID、Worker 集群、连接选项和结果。使用协议兼容的测试服务端时，写明实际引擎和验证范围。

已经确认 CHECK 在本轮达到 `COMPLETE`，并且保存了检查行数、差异数和漏行数时，截图定位超时就按原任务 ID 重新打开详情，只读补拍。

把页面显示的计数和已保存的 `query-job` 结果核对。

## 全量和增量逐笔核对

矩阵开始前列出本轮要跑的源目标组合、全量与增量、模式、时区和对照版本。

交付时按这些维度填实际结果。

Console 写作业和子任务 ID。

实库组件写实际跑到的读写阶段。

没跑的组合标为待验证。

每条读回记录保留阶段、用例标记或主键，以及源端预期和目标实际值。对 LOB 或二进制列，按用例记录实际目标类型、NULL 状态、长度和 SHA-256，并保留原生验证的退出回执。

用例需要对照全量和增量时，先同步并读回一份全量样本。

用对应引擎的日志或状态确认本作业的增量读取已就绪，再写入相同业务值的样本。

走 MySQL binlog 协议时，可以用属于本作业的源库 `Binlog Dump` 连接辅助确认。

增量端到端结果以目标读回为准。

核对时间戳时，用数据库原生 UTC 时间，或以秒为单位的 epoch 读回。

在 TSV 中用 `full-<case>` 和 `cdc-<case>` 关联同一用例。

记录 `phase`、`source_utc`、`target_utc` 和 `delta_seconds`。

时间文本没有明确偏移时，先在查询端统一为 UTC。

用例同时比较 `DATETIME` 时，加上 `datetime_equal` 列。

`1` 表示目标值与源值相同。

```sh
python3 scripts/check_console_jobs.py phase-readback "$directory/compare.tsv" --expect correct
python3 scripts/check_console_jobs.py phase-readback "$directory/compare.tsv" --expect same-results
```

`correct` 要求两阶段的时间戳都与源值相同。

`same-results` 核对两阶段每对样本的目标时间戳。

脚本按时刻比较，并用读回值核对偏差。

提供 `datetime_equal` 时，两种模式都检查 `DATETIME` 是否与源值相同。

需要比较两个都偏离源的 `DATETIME` 时，保留实际值。

两阶段都失败时，仍要报告各自错在哪一笔。

汇报用表格。列出阶段、源库到目标库、实际时区、任务配置、版本、目标读回和出错位置。误配和已知失败用例各自标出。

## 发布前的 Worker 快照

持有目标槽位预留后，记录本轮检查开始时间 `IDLE_CHECK_UTC`。

取得 `CONSOLE_ORIGIN` 和待重启的 `WORKER`。

沿用原预留发布新产物时，仍重新采集。

在能看到全部任务的 Console 账号里，按这个 Worker 查任务。

清除任务名、状态、数据源等额外筛选。

采集全部页。

每份 `listbypage` 成功响应单独保存为 `{requestUrl, workerIp, capturedAt, data}`。

`requestUrl` 取实际 HTTP 请求 URL。

`workerIp` 取实际列表请求的 Worker 筛选。

按 `workerId` 过滤时，用 `workerId` 替代。

`capturedAt` 记录收到响应的 ISO 8601 时间和时区。

保留响应 `data` 的 `allJobCounts` 和 `jobVos`。也保留核对任务状态需要的子任务和子作业字段。空列表同样记录实际使用的 Worker 筛选。

对列表外的已知任务，用同槽位的 `queryjob` 补查。

按相同结构存请求 URL、采集时间和 `data`。

从该任务已知的 Worker 归属记录同一个 `workerIp` 或 `workerId`。

在 [发布流程](mini-release.md) 里把所有页面和补查结果交给 `idle` 命令。

## 待办

CHECK 向导自动化还没做。等源库选择在页面上生效并稳定后，再选目标库，并复核目标库选择仍然有效。按实际库表定位 CHECK 结果行并截图。
