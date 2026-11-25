---
name: cc-setup
description: Fork 之后填写自己的 Mini，安装 Tailscale，把技能链到 Codex，并按本机 TOML 配置 Codex 子代理。用于第一次安装、换机器，或 ssh 连不上 Mini 的时候。
---

# CloudCanal 开发环境

先 fork 这个仓库。不要提交 `mini.env`，也不要拷贝别人的那份文件。一份文件只描述一台测试机。

## 填写 mini.env

把本目录的 `mini.env.example` 复制成 `mini.env`。按这个顺序填四个值。

1. 安装 Tailscale。macOS 运行 `brew install --cask tailscale`，然后打开菜单栏里的 Tailscale。Linux 运行 `curl -fsSL https://tailscale.com/install.sh | sh`。`tailscale status` 已经显示本机在线时，跳过安装。
2. 运行 `tailscale up`。把打印出的登录链接交给用户，由用户在浏览器里加入自己的 tailnet。不要向用户要 Tailscale 密码，也不要在对话里填写。链接过期就再跑一次。
3. 从 `tailscale status` 把测试机的 MagicDNS 名字写入 `MINI_TAILSCALE_NAME`。把它的登录账号写入 `MINI_SSH_USER`。把你要用的 SSH 别名写入 `MINI_SSH_HOST`，常用 `mini`。
4. 用这三个值写 `~/.ssh/config`：

```sshconfig
Host <MINI_SSH_HOST>
  HostName <MINI_TAILSCALE_NAME>
  User <MINI_SSH_USER>
```

不要把 Tailscale IP 写进这个文件。

5. 运行 `ssh -o BatchMode=yes <MINI_SSH_HOST> 'hostname -s'`。SSH 打出复核链接时，按 [Mini SSH 身份复核](#mini-ssh-身份复核) 继续。
6. 把打印出的短主机名写入 `MINI_HOSTNAME`。

`run_mini_test.py` 和 `slot_claim.py` 读这个文件。任一值为空，或远端短主机名和 `MINI_HOSTNAME` 不同，它们就拒绝执行。

Console 会话和 Lab 页面验收按 `MINI_HOSTNAME`、`MINI_TAILSCALE_NAME`、`MINI_SSH_HOST` 中的完整主机名识别 Mini。`run_mini_test.py` 会从这份文件把三个名称传给 Mini 上的测试进程。

## Mini SSH 身份复核

在 Google Chrome 打开 SSH 返回的 Tailscale 复核链接，优先使用 Chrome 已有的 Google 登录完成复核，成功后重试原 SSH 命令。需要用户本人操作时，保留当前链接并交给用户。

## 链接技能

在仓库根目录运行 `sh cloudcanal-dev-test/skills/cc-setup/scripts/link-skills.sh`。脚本把 `pstack`、`cloudcanal-dev-test`、`datasource-lab`、`cloudcanal-console-automation` 链到 `~/.codex/skills/`。已经指向当前技能目录的软链会跳过。指向同一检出中 `.codex/skills/` 下同名旧目录的软链会迁移。脚本也能修复以检出目录名开头的断链，例如 `my-skills/.codex/skills/pstack`，前提是安装目录下没有另一个同名检出。遇到已有目录或其他链接时，脚本会报告需核对的路径并退出。

新开一个对话，确认这四个技能都在。工作区规则在 [编码约定](../../references/coding-workflow.md#工作区规则)。

## Codex 代理

Cursor 的 `/setup-pstack` 写 `~/.cursor/rules/pstack-models.mdc`。Codex 派生子代理时不读那个文件，读 `~/.codex/agents/` 里的 TOML。本目录 `codex-agents/` 是一份可用副本。本机还没有这些文件时，把其中五个 TOML 复制到 `~/.codex/agents/`。

| pstack 角色 | Codex 代理 | 模型 | 档位 |
| --- | --- | --- | --- |
| `feature, refactoring`、`bug-fix`、`perf-issue`、`hillclimb` | `pstack_builder` | `gpt-6.2-astra` | `high` |
| `judgment and prose` | `pstack_judgment` | `gpt-6.2-sol` | `high` |
| `swarm workers` | `pstack_worker` | `gpt-6.2-sol` | `medium` |
| `arena runners` | `pstack_builder`、`pstack_worker`、`pstack_judgment` | 见各代理 | 见各代理 |
| `arena cross-judge pool` | 没有第二家模型时，由主 agent 汇总候选证据并注明评审范围。 |  |  |
| `interrogate reviewers` | `pstack_code_review`、`pstack_worker`、`pstack_regression_review` | `gpt-6.2-astra`、`gpt-6.2-sol`、`gpt-6.1-terra` | 均为 `medium` |

Codex 能按名称委派时，用上表的代理名。只接受模型和档位时，从对应 TOML 读出 `model` 和 `model_reasoning_effort`。第一行按 Poteto 的要求指向 `worker.md`。需要完整会话历史时，继承主会话的模型和档位。同一 Mini 槽位的发布与重启由一位执行者串行运行，见 [mini-release](../../references/mini-release.md)。不同槽位可以并行。

提交技能正文、模板和脚本。缓存、预览图、生成的 PDF 和临时目录留在本机。

单测、JDBC 和测试进程在 `mini.env` 写明的那台机器上跑，入口是 [run_mini_test.py](../../scripts/run_mini_test.py)。Air 和 Pro 只做开发和构建。数据库和每周一上午 9 点的巡检在 [datasource-lab](../../../datasource-lab/SKILL.md)。槽位和 Console 端口在 [mini-release](../../references/mini-release.md)。Console 会话在 [cloudcanal-console-automation](../../../cloudcanal-console-automation/SKILL.md)。
