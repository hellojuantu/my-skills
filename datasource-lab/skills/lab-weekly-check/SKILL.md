---
name: lab-weekly-check
description: 按 Datasource Lab 做每周只读巡检并写出 Mini CHECK 报告。用于定时巡检，不用于发布 MotherData 或手工装库。
---

# Datasource Lab 每周巡检提示词

每次运行先读取 [Datasource Lab 技能](../../SKILL.md) 和工作区 `AGENTS.md`，按技能中的每周巡检和磁盘检查流程执行。

1. 从 MotherData 全量清单和 Lab 的 Mini 手工实例台账开始，核对私有连接及各 CloudCanal 槽位。按各 scope 归档完整候选快照，执行认证只读探测，核对上次与本次差异。引用已有的槽位 Worker 页面证据并注明测试时间。缺少本轮页面证据的条目标记本轮未测。只读巡检跳过已登记数据源的 `Test Connection`，该操作可能更新关系库的版本元数据。
2. 在同一轮运行 Mini 的 `disk-status.py --weekly`，核对 macOS 和 Colima 数据盘、Docker 容器卷和镜像、槽位库占用。检查已结束的临时环境是否留下孤立数据源和容器。核对任务、登记、容器状态及挂载引用，列出精确清理候选及预计释放量。
3. 按 [Mini CHECK 报告模板](../../references/check-report.md) 出一份报告，列出数据源、Worker、磁盘、孤立资源、失败与恢复，以及每项待确认操作。报告列出检查时间、范围、阻塞和原始脱敏证据位置。
4. 定时任务只做读检查和证据归档。发布可用清单、修改配置、部署、重启和清理等操作逐项进入报告，等用户确认。执行已确认范围前重新核对现场，执行后补齐验证结果。
