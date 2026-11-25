# my-skills

我在 Codex 里常用的一组个人 skills。

这个仓库主要用来整理、版本管理和同步我本地在用的技能。仓库里的目录结构与本地 `~/.codex/skills/` 保持一致，方便直接对照和迁移，但这里不会提交运行缓存、临时输出和系统垃圾文件。

## 当前收录

- `travel-guide-xhs`：小红书优先的旅行攻略与路线报告
- `pdf`：PDF 阅读、生成和版式检查
- `playwright`：浏览器自动化
- `playwright-interactive`：持续交互式浏览器调试
- `screenshot`：桌面截图
- `imagegen`：图片生成与编辑
- [`pstack`](.codex/skills/pstack/README.md) 提供 Poteto 原版工作流和子技能。
- [`cloudcanal-dev-test`](.codex/skills/cloudcanal-dev-test/SKILL.md)：原 `cloudcanal-air-test`。Air 或 Pro 开发和构建，Mini 固定槽位发布 JAR，使用 Poteto 协作并在真实 Console 做实库验收。
- [`cloudcanal-console-automation`](.codex/skills/cloudcanal-console-automation/SKILL.md) 提供已登录 Console 的数据源、任务和配置操作。
- [`datasource-lab`](.codex/skills/datasource-lab/SKILL.md)：通过 MotherData 创建和维护 Mini 测试数据库，登记连接，执行每周巡检，并指导 CloudCanal 从 MotherData 添加数据源。

## 目录结构

```text
.
├── .codex/
│   └── skills/
│       ├── cloudcanal-console-automation/
│       ├── cloudcanal-dev-test/
│       ├── datasource-lab/
│       ├── imagegen/
│       ├── pdf/
│       ├── playwright/
│       ├── playwright-interactive/
│       ├── pstack/
│       ├── screenshot/
│       └── travel-guide-xhs/
├── .gitattributes
├── .gitignore
└── README.md
```

## 使用方式

把所需的 skill 逐个链接到本机的 `~/.codex/skills/`。

例如只链接一个 skill：

```bash
mkdir -p ~/.codex/skills
ln -s /path/to/my-skills/.codex/skills/travel-guide-xhs ~/.codex/skills/travel-guide-xhs
```

如果是整体同步，也可以直接复制 `.codex/skills/` 里的内容。

## 在 Air 或 Pro 设置 CloudCanal 技能

### 安装和发现

1. 在开发机准备 Codex、Git、Python 3、OpenSSH 和项目使用的 JDK 17。将本仓库检出到本机后，在其目录内运行下面的命令。重复运行可复用已指向本仓库的链接，遇到其他安装会报出冲突路径。

   ```sh
   (
     set -eu
     repo_dir=$(git rev-parse --show-toplevel)
     skills_dir="$HOME/.codex/skills"
     for skill in pstack cloudcanal-dev-test datasource-lab cloudcanal-console-automation; do
       source_dir="$repo_dir/.codex/skills/$skill"
       destination="$skills_dir/$skill"
       expected=$(cd "$source_dir" && pwd -P)
       if [ -e "$destination" ] || [ -L "$destination" ]; then
         actual=$(cd "$destination" 2>/dev/null && pwd -P || true)
         if [ ! -L "$destination" ] || [ "$actual" != "$expected" ]; then
           printf '已有技能路径，请先核对：%s\n' "$destination" >&2
           exit 1
         fi
       fi
     done
     mkdir -p "$skills_dir"
     for skill in pstack cloudcanal-dev-test datasource-lab cloudcanal-console-automation; do
       destination="$skills_dir/$skill"
       if [ ! -L "$destination" ]; then
         ln -s "$repo_dir/.codex/skills/$skill" "$destination"
       fi
     done
   )
   ```

2. 在 `cc-all-in-one` 保留工作区的 `AGENTS.md`，把其中的技能和参考文档链接对到本机安装路径。首次设置时应包含代理角色映射、反向合并 `dev`、提测模板、提交前格式化以及真实 Console 验收和登录交接。对照 [编码约定](.codex/skills/cloudcanal-dev-test/references/coding-workflow.md) 核对工作区规则。使用 pstack 并行代理时，从已配置的开发机同步对应的 `~/.codex/agents/pstack-*.toml`，或按 [Codex 代理模型表](.codex/skills/cloudcanal-dev-test/references/codex-agent-models.md) 配置本机可用的模型和档位。迁移旧安装时，也要检查 `~/.codex/config.toml` 中已有的技能启用或禁用路径是否指向新位置。
3. 在 `cc-all-in-one` 打开一个新 Codex 对话，确认能选择 `cloudcanal-dev-test`、`datasource-lab`、`cloudcanal-console-automation` 和 `pstack:poteto-mode`。运行 `ssh mini 'pwd'` 并核对本机能通过 `mini` 主机名访问需要的 Console。首次登录、SSO 或身份复核由用户完成。

按使用场景准备外部依赖。Java 提交前使用 IntelliJ IDEA 的 `canal-format`。使用 IDEA 自动化时，另行安装 `pika-idea-control` 和 IDEA 侧的 `Pika Control` 插件。使用 [Console 自动化](.codex/skills/cloudcanal-console-automation/SKILL.md) 导入数据源时，使用 `login --save-cookie` 为对应槽位保存的会话。Mini 上的实际运行目录为 `~/datasource-lab`，连接记录、凭据、会话、历史快照、发布包和巡检报告留在其私有存储中。

在负责巡检的开发机上，把 Codex 的 `datasource-lab 每周巡检` 关联到 `cc-all-in-one`。沿用本仓库的 [每周巡检提示词](.codex/skills/datasource-lab/references/weekly-check-prompt.md) 和 [Mini CHECK 报告](.codex/skills/datasource-lab/references/check-report.md)。当前 Lab 在每周一上午 9 点巡检，首次设置可手动跑一轮，核对 Mini 上的私有报告和候选快照。

### 开发和验收

1. 在 Air 或 Pro 明确用例、涉及仓库和版本，按 `cloudcanal-dev-test` 实现和复核。需要代理并行处理时先核对 pstack 角色映射。
2. 在 Mini 运行相关单元和 JDBC 组件测试。需要部署代码时在开发机的独立目录构建，按槽位登记选择空闲槽位或新增槽位，备份、替换 JAR、重启并核对 Worker 状态和产物哈希。用现有版本验收时直接进入对应的 Mini Console。 [Mini 槽位发布](.codex/skills/cloudcanal-dev-test/references/mini-release.md)
3. MotherData 创建并管理测试库。Datasource Lab 在 Mini 私下登记连接并统一按周巡检。CloudCanal 按选定的 MotherData 数据源 ID 获取当前连接，在目标槽位添加或复用登记并验证 Worker 连通性。 [Datasource Lab](.codex/skills/datasource-lab/SKILL.md)
4. 通过真实 Console 建立并运行任务，记录任务 ID、页面结果和目标端读回数据。按用例验证全量、CDC 与独立 CHECK。 [页面取证](.codex/skills/cloudcanal-dev-test/references/browser-job.md)

## 维护约定

- 优先提交 skill 本体、模板、脚本和引用规范
- 不提交缓存、预览图、生成 PDF、临时目录和系统文件
- 尽量让文档、模板和脚本行为保持一致
