---
name: cloudcanal-console-automation
description: 通过 CloudCanal Console 登录会话和前端接口自动化操作。用于管理和测试数据源、创建数据任务、修改订阅或任务配置、启停或重跑任务、调整调度或位点，以及使用临时数据和一致性校验做 N×N 链路测试。
---

# CloudCanal 控制台自动化

## 按 Console 前端行为执行

使用 Console 前端接口。处理未验证的数据源组合前，核对实际前端请求、动态 WebOp 或生成的请求体。按各引擎实际支持的层级、映射和连接配置构造参数。

CloudCanal 功能变更的 Mini 页面验收按 [CloudCanal 开发与实库验收](../cloudcanal-dev-test/SKILL.md) 执行。本技能负责 Console 接口操作与批量链路测试。

在本技能目录下运行脚本。

```bash
export CLOUDCANAL_SKILL="${CLOUDCANAL_SKILL:-$PWD}"
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" --help
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" doctor
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-selftest
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-plan --test-mode dev
```

自动化登录使用 `sm-crypto` 加密密码。可将 `SM_CRYPTO_NODE_MODULE_DIR` 指向包含依赖的 `node_modules`。脚本也从当前目录向上查找，并读取 `CLOUDCANAL_WEB_DIR` 或 `CLOUDCANAL_REAKH_DIR`。

Mini 上按 [发布槽位登记](../cloudcanal-dev-test/references/mini-release.md) 确认 Console 端口，复用同槽位自动化会话。缺少有效会话时，用 `login --base-url "$CC_BASE_URL" --save-cookie "$CC_COOKIE_FILE"` 登录，后续命令传 `--cookie-file "$CC_COOKIE_FILE"`。已授权的 CLI 登录按顺序读取 `--account` 和 `--password`、`CC_ACCOUNT` 和 `CC_PASSWORD`、交互输入。遇到登录页、单点登录或身份复核时交给用户完成。凭据和会话文件放在仓库外，会话文件权限为 `0600`。

首次配置时运行 `doctor` 和 `autotest-selftest`。`doctor` 检查 Python、Node、`sm-crypto`、可选的 `clouddm-web` 工作区、会话和 Console 地址。加 `--check-api` 可查询默认集群。`autotest-selftest` 在本地验证自动化任务各阶段的编排。

## 操作流程

1. 确认 Console 地址、同槽位会话和 Worker 集群，使用 `--base-url`、`--cookie-file` 和适用的 `--cluster-id`。
2. 写入前查询本次操作涉及的动态定义，例如数据源 KV、任务额外配置、映射规则和 WebOp 位点表单。
3. 创建、编辑、更新、调位点或调度前，先用 `--dry-run` 核对请求。
4. 测试环境实写时优先使用临时任务和数据源。经用户授权后，按[清理步骤](references/validation.md#cleanup-only-when-requested-by-the-user)处理临时对象。
5. 创建或编辑后查询已保存的对象。需要验证数据源连接时，单独运行连接测试。
6. 创建结构、全量和增量任务后核对状态。结构已完成、`fsmActive=false` 且后续任务仍处于 `INIT` 时，通过 `continue-job` 走前端的 `fsmStart` 流程。

Mini 链路测试优先用 Lab 已登记的数据库。需要新实例时按 [Datasource Lab](../datasource-lab/SKILL.md) 在 Mini 准备，再用 Automation 执行 Console 登记和任务操作。环境巡检按 [Mini CHECK 报告](../datasource-lab/references/check-report.md) 记录只读结果，执行报告中的变更前由用户确认范围。

N×N 链路测试中，`ROUTED` 表示前端或注册表识别该数据源类型，可以构造数据源或任务请求。`READY` 表示适配器能在真实环境准备临时对象、生成源端变更、做本地计数或摘要核对并清理。常规批量验证选用 `READY` 组合。用户明确要求覆盖未就绪组合并接受现成数据或仅做 CloudCanal CHECK 时，按约定缩小验收范围。

`autotest-run` 和 `autotest-batch-run` 启动或继续任务，按实际阶段等待全量完成和增量就绪，收集本地计数、CloudCanal CHECK 结果和 `ERROR` 日志。临时测试数据默认执行 1,000 轮 faker 变更。传 `--table` 或 `--table-map` 时跳过这一步，一致性检查仍可通过。要验证该路径的增量交付，在读端就绪后写入带标记的样本，再从目标端读回。用 `--no-*` 明确缩小本轮范围。

创建任务时会复制数据源连接字段和专用配置，已有任务继续使用创建时保存的值。修复失败的旧任务时，通过 `list-job-configs` 查询相关字段，核对 `endPointType` 和 `configType`。用 `update-job-configs` 修正受影响的 `SOURCE` 或 `TARGET` 下的 `DATASOURCE` 配置，再通过 `operate-console-job --action retry` 重试失败的异步操作。若样本建在旧地址上，重建测试数据或任务后再验证。

前端接口还没有专用子命令时，用 `list-services` 确认服务键，再用 `call-service --service ... --payload-json @file --dry-run` 核对请求。只有原始请求路径时，用 `call-api --path ...`。流程高频复用后再封装专用命令。

## 操作参考

- [数据源创建、更新、删除和连接测试](references/datasource.md)
- [创建任务和修改订阅](references/datajob.md)
- [任务操作、配置、调度和位点](references/operations.md)
- [N×N 链路测试、临时数据、faker CRUD、一致性校验和报告](references/autotest.md)
- [前端请求与引擎特例](references/frontend-parity.md)
- [验收和清理](references/validation.md)

## 报告范围

按实际验证过的数据源、组合和阶段汇报。需要补前端请求或 `--dry-run` 对照时，在结果里列明。
