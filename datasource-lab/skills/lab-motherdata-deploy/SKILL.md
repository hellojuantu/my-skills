---
name: lab-motherdata-deploy
description: 把 MotherData 的 master 发布到 Mini，包含隔离的 Flyway 验证和切换。用于升级 MotherData，不用于每周巡检。
---

# 从 master 发布到 Mini

## 1. 锁定源码和运行状态

从 [MotherData 的 Gitee 仓库](https://gitee.com/clougence/motherdata) 取 `refs/heads/master`，记下完整提交 SHA。

用独立构建目录。

看 Mini 现有 checkout 和部署配置。

保留工作区里未提交的修改。

确认 Mini 的 `master` 可以快进到目标 SHA。

Mini 没有 Gitee 凭据时，在已经有授权 Git 会话的 Air 或 Pro 上取目标提交。

传一个带可验证 Git 历史的 bundle。

Mini 先验证 bundle，再抓取并核对 SHA 和快进关系。

不要传 Git 凭据。

从 `compose.yaml`、`start.sh` 和正在运行的容器确认当前镜像、共享网络和持久 MySQL。

保存健康检查、应用记录和 `flyway_schema_history` 基线。

确认目标提交的最新 migration。

看它对当前版本之后各 migration 的改动。

比对已经应用的 migration 内容。

## 2. 构建和实测迁移

1. 按目标提交的项目说明，用锁文件构建前端。用 JDK 17 打包后端 boot JAR 和外部插件。跑该版本的前后端测试。测试基础设施失败和应用失败分开记。
2. 用源码里的 `deploy/docker/Dockerfile` 和同目录入口脚本构建 `linux/arm64` 镜像。
   构建上下文包含 `motherdata.jar`、`plugins/` 和 `docker-entrypoint.sh`。
   核对 `RUNTIME_IMAGE` 的架构。
   选用和 Mini 已验证部署兼容的 ARM64 JRE。
   镜像标签含提交短 SHA。
   `org.opencontainers.image.revision` 记录完整 SHA。
   在构建端导出镜像时先记录 SHA-256。
   传到 Mini 后先验证文件，再导入。
   核对导入镜像的平台和提交。
3. 只备份 `motherdata` 库到 Mini 的私有目录。
   在 Mini 的独立 Docker 网络里启动临时 MySQL，用临时凭据。
   按 [手工部署到 Mini](../../SKILL.md#手工部署到-mini) 登记。
   把副本恢复到该实例。
   用新镜像接入。
   由应用在启动时执行 Flyway。
   检查预期 migration 都成功，前端和 API 正常，节点、数据源和安装记录的核验结果符合 migration 预期。
   只删掉这次创建的临时容器和网络。

## 3. 切换和复核

1. 确认发布已授权，实测迁移通过，并且没有仍在安装或清理的数据库任务。
   记下旧镜像和配置。
   暂时停掉 MotherData 应用。
   对 `motherdata` 库再做一份切换前备份，记录 SHA-256。
   备份和部署记录留在 Mini 的私有目录。
2. 更新持久 Compose 的镜像和启动脚本。
   用 `docker compose up -d --no-deps --pull never motherdata` 只重建 MotherData 服务。
   保留现有共享网络、数据库连接设置和 MySQL 容器。
3. 从 Air 或 Pro 访问 `http://mini:8765/`。
   核对首页、`/actuator/health`、关键记录和最新成功的 Flyway 版本。
   核对实际运行容器的镜像 SHA 和目标提交。
   检查 CloudCanal 的共享基础设施仍然正常。
   验证通过后，把 Mini 源码快进到已发布的提交。
   报告实际提交、迁移起止版本、验证结果和私有备份路径。

切换失败时，先看 Flyway 历史和数据库状态。

确认数据库没有发生不兼容变化之后，才恢复旧配置和镜像。

迁移已经推进，或状态无法确定时，保留当前证据和数据库备份。

任何覆盖式恢复之前，向用户说明受影响的对象，并确认恢复方案。
