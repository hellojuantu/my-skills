---
name: datasource-lab
description: 在 Mini 优先通过 MotherData 安装和维护 CloudCanal 测试数据库，登记缺少模板时的临时手工实例，巡检数据库和磁盘，并将已验证的数据源接入 CloudCanal 槽位。
---

# 数据源实验室

用 `mini.env` 里的 `MINI_SSH_HOST` 进入 `~/datasource-lab`。

这里放台账、完整快照、已发布的可用清单和巡检记录。

CloudCanal 的新测试库都装在 Mini 上，包括一次性复现和临时容器。

SSH 要身份复核时，按 [Mini SSH 身份复核](../cloudcanal-dev-test/skills/cc-setup/SKILL.md#mini-ssh-身份复核) 继续。

先看 MotherData 里已有的安装和可用模板。

版本、架构和用例都满足的已验证实例，直接复用。

有适用模板时，在 MotherData 里安装。

以前安装失败过，先查原因。

没有适用模板时，才在 Mini 上临时手工部署。

在 Lab 台账里记下缺的模板、临时用途，以及以后要放进 MotherData 的事。

巡检覆盖 MotherData 托管的实例，以及 Lab 登记的手工实例。要接入 CloudCanal 时，记下各槽位的数据源 ID 和 Worker 连接结果。

## 手工部署到 Mini

在本 skill 目录运行 `python3 scripts/check-deployment-route.py http://mini:8765 <引擎>`。

主机名以 `mini.env` 为准。

名字不是 `mini` 时，换成那个名字。

退出码 `1` 表示用输出里的 MotherData 模板。

退出码 `0` 才进入临时手工流程。

退出码 `2` 表示先查清目录或参数错误。

只有用例明确要求某个镜像时，才加 `--exact-image 镜像:标签`。

模板安装失败时，按原记录查节点、安装条件或资源。

1. 通过 `ssh mini` 在 Mini 上部署需要的版本和配置。启动前看现有测试实例、端口和磁盘。直接部署的实例由 Datasource Lab 管理。
2. 在 `host-locations.json` 的 `instances` 里登记稳定的 `labRecord`。
   记下引擎、版本、安装主机、访问入口、容器或服务名、用途和验收证据。
   临时实例也登记，并记下生命周期和清理状态。
   连接凭据放在权限为 `0600` 的 `private/connections.local.json`，用同一个 `labRecord` 关联。
3. 实测这个实例的连接，以及用例需要的读写。
   要接入 CloudCanal 时，在已授权的槽位登记连接并验证 Worker。
   手工实例用 Lab 记录。
   MotherData ID 留给它托管的实例。

## MotherData 数据库创建与维护

MotherData 入口是 `http://mini:8765/`。

服务目录是 `~/datasource-lab/motherdata-service/`。

升级应用时按 [Mini 发布流程](skills/lab-motherdata-deploy/SKILL.md) 锁定 Gitee `master` 提交。

在隔离副本上验证 Flyway，再备份切换。

MotherData 元数据在共享 MySQL 的 `motherdata` 库。

发布按单个服务切换。

在本 skill 目录执行 `python3 scripts/check-service.py http://mini:8765`。

核对健康状态、节点、安装记录和数据源 ID。

部署前后比对同一组记录，并看 Mini 入口首页。

在 MotherData 里选 Mini 节点、数据库类型、驱动、架构和端口。

先核对现有安装。

接管实例时保留数据，并核实安装主机。

常驻库按已经给出的链路优先级和已验证清单来排。

安装完成后核验真实连接和读写，再登记到 Lab。

卸载数据库，或清理卷和镜像之前，向用户确认具体对象。

## 登记 MotherData 连接

安装、接管或变更连接之后，从 MotherData 核对并更新 Mini 的 `private/motherdata-connections.local.json`。

这个文件集中放各引擎的私有连接记录。

权限是 `0600`。

每个实例一条。

内容是 JSON 数组。

每条记录包含这些字段：`id`（MotherData 数据源 ID）、`scope`（`motherdata`）、`motherDataInstallId`、`type`、`host`、`port`、`database`、固定测试账号的 `user` 和 `password`，以及需要的 TLS 信息。

`host-locations.json` 记录安装位置、访问入口和稳定 ID。

账号、密码和密钥留在 Mini 的私有文件里。

巡检报告和 skill 仓库只用脱敏信息。

同步固定账号时，按 MotherData 数据源 ID 查对应安装记录。

从「获取链接信息」取当前凭据。

按同一个 ID 核对 Lab 台账和各槽位登记。

在每个槽位做 Worker 连接测试并记下结果。

凭据只在私有会话或进程里用。

有专项测试时，在对应的 MotherData 托管实例上确认账号和权限。

在 Lab 同一实例记录下的 `testAccounts` 里登记独立标识、用途、目标库、账号和密码。

记下实际使用的 CloudCanal 槽位和数据源 ID。

专项账号沿用原 MotherData 实例 ID。

CloudCanal 使用独立登记，并通过该槽位的 Worker 连接测试。

固定账号字段用于常驻登记和默认巡检。

三处核对从 MotherData 的全量数据源 ID 开始。

同引擎的不同实例各列一行。

逐一核对 Lab 台账和每个 CloudCanal 槽位的登记。

记下匹配的数据源 ID、缺失项和连接验证结果。

CloudCanal 这边优先用已有 ID 映射。

没有映射时，核对引擎、端点、服务名或库名，以及账号。

`commonDefaults` 只决定常用链路优先选哪个实例。

全量同步时逐个补齐。

报告里保留连接失败或待验证的条目。

## CloudCanal 槽位连接验收

添加数据源、发布或全量同步之后，在每个涉及槽位的真实 Console 页面，对本轮涉及实例的常规登记运行 **Test Connection**。

在弹窗里选对应的 Worker 集群和网络入口。

留下页面结果。

手工实例按 `labRecord` 关联证据。

专用账号或额外登记按对应测试用例验证。

这个结果只覆盖所选连接。

数据同步另按任务做目标读回。

从 MotherData 单独采集全量 `motherdata.json`。

把本轮开始时间、各槽位预期的 Worker 集群和常规登记写成 `expected.json`。

`evidence.json` 的 `results` 每项包含 `pageUrl`、`instanceId`、`cluster`、`status` 和带时区的 `testedAt`。

页面显示连接成功时，把 `status` 记为 `Successful`。

保留原始页面证据。

三个文件只用脱敏字段。

默认检查 8111 和 8112 的全部 MotherData 数据源。

单槽位验收时，从 [Mini 槽位登记](../cloudcanal-dev-test/references/mini-release.md) 读取 `consolePort`，传给 `--slot`。

每个待验数据源传一个 `--source-id`，并在 `expected.json` 的该槽位列出对应登记。

手工实例传 `labRecord`。

只验手工实例时，MotherData 导出的 `dataSources` 可以为空。

下面的例子核对只加到 8111 的两个数据源。

```json
{"notBefore":"2026-11-23T09:00:00Z","slots":{"8111":{"cluster":"Default Cluster","sources":{"5":"ora-26ai","6":"ora-19c"}}}}
```

```sh
python3 scripts/check-service.py http://mini:8765 > motherdata.json
python3 scripts/check-slot-connections.py motherdata.json expected.json evidence.json --slot 8111 --source-id 5 --source-id 6
```

每个涉及槽位的全部待验实例，都要有本轮 Worker 的 `Successful` 结果。

`check-slot-connections.py` 用全量目录核实 ID，再校验所选范围的槽位页面、登记、Worker 集群、结果和时间。

缺失或失败时，按槽位和实例保留原始提示，并用实测结果更新验收状态。

## 每周数据源巡检

定时任务在每周一上午 9 点跑 [每周巡检](skills/lab-weekly-check/SKILL.md)。

把数据源、Worker、磁盘和孤立资源汇总到同一份 [Mini CHECK 报告](references/check-report.md)。

CHECK 阶段用只读探针，并归档证据。

已登记关系库的 Console **Test Connection** 可能更新数据源版本元数据。

把它放在发布或登记验收时做。

实施操作前，按报告编号取得用户确认。

1. 读 Mini 的这些文件：`README.md`、`host-locations.json`、`private/motherdata-connections.local.json`、`private/connections.local.json`、`private/datasources-247.local.json`、`private/health-checks/latest.json`。
   从 `host-locations.json` 核对仍在使用的 Mini 手工实例。
   按 `labRecord` 查私有连接。
   Air 历史候选取 Mini 的 `private/datasource-locations.json` 里 `Air` scope 的记录。
   完整快照包含各 scope 的全部候选，包括上次掉线的源。
   保留已有 scope 和 ID。
   手工实例保留 Lab 记录标识。
   合并等价探测，再把结果逐条映射回快照。
2. 台账分别记录数据库的安装主机、访问入口、探测主机和证据时间。
   仍经 Air 转发的历史端点，沿现有配置核实上游宿主机或容器。
   只看到监听端口时，把安装位置记为待核实。
   LAN 实例同样记录物理宿主。
   Mini 容器和 Worker 可达性从 Mini 实测。
   原主机的回环服务在相应主机上测。
3. 从归档的连接记录读取账号和指定库。
   用 Mini `private/health-venv` 里的驱动，或已有的原生客户端，做最小的认证只读操作。
   MySQL、PostgreSQL、SQL Server 选定目标库后执行 `SELECT 1`。
   Oracle 按登记服务名连接后执行 `SELECT 1 FROM DUAL`。
   HANA 用 `SELECT 1 FROM DUMMY`。
   MongoDB 和 Redis 做认证 ping。
   Elasticsearch 查集群健康。
   Catalog 列命名空间。
   Kafka 读 broker 元数据。
   复用 Mini 的 `probe_connections.py` 时导入 `probe` 函数，避开会覆盖已发布清单的命令行入口。
   用这个函数探测 Oracle 时，把台账的主机、端口和服务名组成 `host:port:service`，传入 `privateHost`。
   有的驱动只连默认库，还要额外验证所登记的库。
   端口可达、驱动缺失、权限错误、未测和纯文件项分开归类。
   瞬时网络错误限次重试。
4. 每次在 `private/health-checks/` 建一个用 UTC 时间命名的私有归档。
   每个 scope 先归档完整候选文件。
   探测始终从这份归档开始。
   在报告的 `summary.snapshotSha256ByScope` 里记录 scope 对应归档文件的 SHA-256。
   保留各条结果、起止时间、重试次数、安装位置、测试位置、上次发布版本和这次差异。
   汇总按主机列出通过、失败、恢复、未测和原因。
   验证完整后原子更新 `latest.json`。
   完整快照和凭据只存在实验室。
   周报只列必要的脱敏证据。
5. 拟议可用清单只包含这次实测通过且仍启用的候选。
   标明建议移出的条目，以及恢复后建议加回的条目。
   核对 MotherData 实例和在用手工实例在各槽位的登记。
   引用已有 Worker 结果，并注明测试时间。
   缺少本轮槽位证据时，标记本轮未测。
   做完本轮 [磁盘和孤立资源检查](#磁盘镜像与清理确认)。
   源快照和往期清单一直保留。
   发布、配置修复和清理按报告逐项等用户确认。
   确认后，核对台账是否仍对应该次快照。
   改过连接地址、目标库或认证配置的记录必须重新实测。
   备份当前版本后原子发布，再核对 ID 和条数。

可以从 Air 或 Pro 的 skill 目录做只读比较。

把 `RUN_UTC` 换成实际归档目录名。

按各自 scope 比对完整覆盖和快照摘要，输出待加入和移出的 ID。

退役和停用标记以台账为准。

没有快照摘要的历史报告只能用 `--historical` 看候选差异。

发布需要重新实测，并生成关联快照的报告。

```sh
ssh -o BatchMode=yes mini 'cd ~/datasource-lab && /usr/bin/python3 - private/health-checks/RUN_UTC/datasources-247.json private/usable-datasources.local.json private/health-checks/RUN_UTC/report.json' < scripts/list-delta.py
```

## 槽位首次导入或补齐数据源

批量准备客户常用链路时，从 Mini 的 `datasource-fixtures/catalog.json` 读取 `commonDefaults`。

选取经过实测的 MotherData 数据源 ID。

向指定 CloudCanal 槽位添加时，从 MotherData 按 ID 取当前连接配置。

手工实例按 `labRecord` 从 Lab 私有台账取配置。

核对类型、目标库、访问端点和 Worker。

经授权后在 Console 创建或复用登记，做 Worker 连接测试，并记下实际 CloudCanal 数据源 ID。

`mysql-pair` 隔离专项用 `datasource-fixtures/catalog.json` 的稳定键引用源和目标。

读取目标槽位 `cloudcanal-service/private/slot-01/source-plan.json` 或 `slot-02/source-plan.json`。

核对分支、库后缀、访问端口和 Worker。

在 Air 或 Pro 上先预览计划。

```sh
ssh -o BatchMode=yes mini 'cat ~/datasource-lab/datasource-fixtures/seed-run.py' | python3 - --slot 01
```

已经授权应用 `mysql-pair` 时，用同一条命令，并向 Python 加 `--cookie-file "$SESSION_FILE"`。

用 [Console 自动化](../cloudcanal-console-automation/SKILL.md) 的 `login --save-cookie`，为同一槽位保存私有会话。

导入器按稳定 `instanceId` 创建或复用登记。

复用前，核对该槽位已保存的默认库和计划相同。

唯一性或配置冲突时停止。

在已登录的真实页面用 Worker 集群测试连接。

记下实际 CloudCanal 数据源 ID。

JAR 发布复用槽位元数据库和已有登记。

分支部署和真实页面验收用 [CloudCanal 开发与实库验收](../cloudcanal-dev-test/SKILL.md)。

## 磁盘、镜像与清理确认

```sh
ssh -o BatchMode=yes mini '/usr/bin/python3 ~/datasource-lab/disk-status.py --weekly'
```

每次巡检记录 macOS 数据盘、Colima 数据盘、容器、卷、镜像和槽位 schema 的占用，并和上次归档比较。

同时核对登记中正在运行的各槽位、共享 Prometheus 和 MotherData 的直连健康状态。

检查已结束且归属明确的 `cc-run-*` 临时环境。

看是否留下孤立数据源或已退出的容器。

查活动任务、CloudCanal 登记和 Docker 引用。

报告分别列出容器 ID、可以独占释放的卷、镜像 ID 和标签，以及估算释放量。

没有被容器引用的镜像，还要核对构建、发版和回退用途。

只执行报告里用户已确认的项目和具体 ID。执行前复查归属、状态和引用。执行后记录实际变化。

技能仓库放程序和操作约定。Mini 的 `private/`、真实目录快照、端点、凭据、会话、发布包和运行报告留在受控机器上。
