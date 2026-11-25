# Poteto 代理模型

本机 Codex 使用 Poteto 的 `medium` 预算。开发和判断角色使用 `high` 推理档位，普通并行执行和独立复核使用 `medium`。模型和档位由 `~/.codex/agents/` 中各角色的 TOML 定义。

| pstack 角色 | Codex 代理 |
| --- | --- |
| `feature, refactoring`、`bug-fix`、`perf-issue`、`hillclimb` | `pstack_builder` |
| `judgment and prose` | `pstack_judgment` |
| `swarm workers` | `pstack_worker` |
| `arena runners` | `pstack_builder`、`pstack_worker`、`pstack_judgment` |
| `arena cross-judge pool` | 跨厂商盲评需要可调用的其他厂商模型。仅用本机 Codex 模型时，由主 agent 汇总候选证据并注明评审范围。 |
| `interrogate reviewers` | `pstack_code_review`、`pstack_worker`、`pstack_regression_review` |

- Codex 工具支持按名称委派时，使用对应的自定义代理。托管 `spawn_agent` 只接受模型和档位时，从该代理的 TOML 读出 `model` 和 `model_reasoning_effort`，写入 `model` 和 `reasoning_effort`，用 `fork_turns="none"` 并在任务正文提供所需上下文。第一行按 Poteto 的要求指向 `worker.md`。需要完整会话历史时，按工具约束继承主会话的模型和档位。
- 按可独立验收的任务数分派，最多占用当前运行时提供的席位。同一 Mini 槽位的发布与重启由一位执行者串行运行，详见 [Mini 槽位发布流程](mini-release.md)。不同槽位可独立执行。
