# 从 master 发布到 Mini

## 1. 锁定源码和运行状态

- 从 [MotherData 的 Gitee 源仓库](https://gitee.com/clougence/motherdata) 取 `refs/heads/master` 并记录完整提交 SHA。使用独立构建目录，检查 Mini 现有 checkout 和部署配置。保留工作区的未提交修改。确认 Mini `master` 可以快进到目标 SHA。
- 如果 Mini 缺少 Gitee 凭据，在已有授权 Git 会话的 Air 或 Pro 获取目标提交，传输包含可验证 Git 历史的 bundle。Mini 先验证 bundle，再抓取并核对 SHA 和快进关系。不要传输 Git 凭据。
- 从 `compose.yaml`、`start.sh` 和运行容器确认当前镜像、共享网络和持久 MySQL。保存健康检查、应用记录和 `flyway_schema_history` 基线。确认目标提交的最新 migration，检查它对当前版本之后各 migration 的改动。比对已应用 migration 的内容。

## 2. 构建和实测迁移

1. 使用目标提交的项目说明，按锁文件构建前端，通过 JDK 17 打包后端 boot JAR 和外部插件。运行该版本的前后端测试。区分测试基础设施失败和应用失败，记录各项结果。
2. 用源码中的 `deploy/docker/Dockerfile` 及同目录入口脚本构建 `linux/arm64` 镜像。构建上下文包含 `motherdata.jar`、`plugins/` 和 `docker-entrypoint.sh`。核对 `RUNTIME_IMAGE` 的架构，选用与 Mini 已验证部署兼容的 ARM64 JRE。镜像标签含提交短 SHA，`org.opencontainers.image.revision` 标签记录完整 SHA。在构建端导出镜像时，先记录 SHA-256，传到 Mini 后验证文件再导入。核对导入的镜像平台与提交。
3. 只备份 `motherdata` 库到 Mini 的私有目录。在 Mini 的独立 Docker 网络中启动临时 MySQL，使用临时凭据，按[手工部署流程](../SKILL.md#手工部署到-mini)登记。把副本恢复到该实例，用新镜像接入，由应用在启动时执行 Flyway。检查预期 migration 均成功、前端和 API 正常，节点、数据源和安装记录的核验结果符合 migration 预期。只移除本次创建的临时容器和网络。

## 3. 切换和复核

1. 确认发布已授权，实测迁移通过，并且没有仍在安装或清理的数据库任务。记录旧镜像和配置，暂时停 MotherData 应用，对 `motherdata` 库再做一份切换前备份，记录 SHA-256。备份和部署记录留在 Mini 的私有目录。
2. 更新持久 Compose 镜像和启动脚本，用 `docker compose up -d --no-deps --pull never motherdata` 只重建 MotherData 服务。保留现有共享网络、数据库连接设置和 MySQL 容器。
3. 从 Air 或 Pro 访问 `http://mini:8765/`。核对首页、`/actuator/health`、关键记录和最新成功 Flyway 版本。核对实际运行容器的镜像 SHA 和目标提交，检查 CloudCanal 的共享基础设施仍正常。验证通过后，把 Mini 源码快进到已发布的提交。报告实际提交、迁移起止版本、验证结果和私有备份路径。

切换失败时先检查 Flyway 历史和数据库状态。确认数据库没有发生不兼容变化后，才恢复旧配置及镜像。如果迁移已推进或状态无法确定，保留当前证据和数据库备份。任何覆盖式恢复之前，向用户说明受影响对象并确认恢复方案。
