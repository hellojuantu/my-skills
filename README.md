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

## 目录结构

```text
.
├── .codex/
│   └── skills/
│       ├── imagegen/
│       ├── pdf/
│       ├── playwright/
│       ├── playwright-interactive/
│       ├── screenshot/
│       └── travel-guide-xhs/
├── .gitattributes
├── .gitignore
└── README.md
```

## 使用方式

如果你希望把仓库里的 skill 挂回本机 Codex，可以把整个目录或单个 skill 链接到 `~/.codex/skills/`。

例如只链接一个 skill：

```bash
mkdir -p ~/.codex/skills
ln -s /path/to/my-skills/.codex/skills/travel-guide-xhs ~/.codex/skills/travel-guide-xhs
```

如果是整体同步，也可以直接复制 `.codex/skills/` 里的内容。

## 维护约定

- 优先提交 skill 本体、模板、脚本和引用规范
- 不提交缓存、预览图、生成 PDF、临时目录和系统文件
- 尽量让文档、模板和脚本行为保持一致
