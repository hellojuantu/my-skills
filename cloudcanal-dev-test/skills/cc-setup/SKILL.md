---
name: cc-setup
description: After a fork, fill in your own Mini, install Tailscale, link the skills into Codex, and configure Codex subagents from this machine's TOML. Use for a first install, a new machine, or when ssh cannot reach Mini.
---

# CloudCanal development environment

Fork this repository first. Do not commit `mini.env`. Do not copy someone else's file. One file describes one test machine.

## Fill in mini.env

Copy `mini.env.example` in this directory to `mini.env`. Fill it in this order.

1. Install Tailscale.
   On macOS, run `brew install --cask tailscale`, then open Tailscale from the menu bar.
   On Linux, run `curl -fsSL https://tailscale.com/install.sh | sh`.
   Skip the install when `tailscale status` already shows this machine online.
2. Run `tailscale up`.
   Hand the printed login link to the user.
   Have the user join their own tailnet in a browser.
   Do not ask the user for a Tailscale password.
   Do not type one in the chat.
   Run the command again if the link expires.
3. From `tailscale status`, write the test machine's MagicDNS name into `MINI_TAILSCALE_NAME`.
   Write its login account into `MINI_SSH_USER`.
   Write the SSH alias you will use into `MINI_SSH_HOST`.
   The usual alias is `mini`.
4. Write `~/.ssh/config` from these three values.
   Do not put a Tailscale IP in that file.

```sshconfig
Host <MINI_SSH_HOST>
  HostName <MINI_TAILSCALE_NAME>
  User <MINI_SSH_USER>
```

5. Run `ssh -o BatchMode=yes <MINI_SSH_HOST> 'hostname -s'`.
   When SSH prints an identity-check link, continue at [Mini SSH identity check](#mini-ssh-identity-check).
6. Write the printed short hostname into `MINI_HOSTNAME`.

`run_mini_test.py` and `slot_claim.py` read this file. They refuse to run when any value is empty, or when the remote short hostname differs from `MINI_HOSTNAME`.

Console sessions and Lab pages recognize Mini by the full hostnames in `MINI_HOSTNAME`, `MINI_TAILSCALE_NAME`, and `MINI_SSH_HOST`. `run_mini_test.py` passes these three names to the test process on Mini.

## Mini SSH identity check

When `run_mini_test.py` or `slot_claim.py` recognizes an identity-check link, it prints the steps to follow in Chrome. Follow those steps and finish the check with a Google account that is already signed in. When you run another SSH command directly, pass this round's link to the same entry point with `python3 cloudcanal-dev-test/scripts/ssh_auth.py '<Tailscale identity-check link returned by SSH>'`.

## Link the skills

From the repository root, run `sh cloudcanal-dev-test/skills/cc-setup/scripts/link-skills.sh`. The script links `pstack`, `cloudcanal-dev-test`, `datasource-lab`, `cloudcanal-console-automation`, and `juantu-mode` into `~/.codex/skills/`.

Skip a link that already points at the matching skill directory in this checkout. Rewrite a legacy `.codex/skills/<skill>` link in the same checkout only when the install directory has no other checkout of the same name. When that same-named checkout is already in the install directory, stop and leave the link. When a link points somewhere else, stop and print the path to check.

Cursor uses the same `juantu-mode`. Link this machine's user skill directory to `my-skills/juantu-mode`. Do not make another copy.

Start a new chat and confirm that all five skills are present. What the workspace requires is in [Workspace rules](../../references/coding-workflow.md#workspace-rules).

## Codex agents

Cursor's `/setup-pstack` writes `~/.cursor/rules/pstack-models.mdc`. Codex does not read that file when it dispatches a subagent. It reads the TOML in `~/.codex/agents/`. The `codex-agents/` directory here is a usable copy. When this machine does not have those files yet, copy its five TOML files into `~/.codex/agents/`.

| pstack role | Codex agent | Model | Effort |
| --- | --- | --- | --- |
| `feature, refactoring`, `bug-fix`, `perf-issue`, `hillclimb` | `pstack_builder` | `gpt-6.2-astra` | `high` |
| `judgment and prose` | `pstack_judgment` | `gpt-6.2-sol` | `high` |
| `swarm workers` | `pstack_worker` | `gpt-6.2-sol` | `medium` |
| `arena runners` | `pstack_builder`, `pstack_worker`, `pstack_judgment` | see each agent | see each agent |
| `arena cross-judge pool` | When there is no model from a second vendor, the main agent gathers the candidate evidence and states the review scope. |  |  |
| `interrogate reviewers` | `pstack_code_review`, `pstack_worker`, `pstack_regression_review` | `gpt-6.2-astra`, `gpt-6.2-sol`, `gpt-6.1-terra` | all `medium` |

When Codex can delegate by name, use the agent names in the table. When you can fill in only a model and an effort, read `model` and `model_reasoning_effort` from the matching TOML. The first line points at `worker.md`, as Poteto requires. When the full session history is needed, inherit the main session's model and effort.

One person runs release and restart on the same Mini slot, one after another. See [mini-release](../../references/mini-release.md). Different slots can run in parallel.

Commit the skill text, templates, and scripts. Leave caches, preview images, generated PDFs, and temporary directories on this machine.

Unit tests, JDBC, and test processes run on the machine named in `mini.env`. The entry point is [run_mini_test.py](../../scripts/run_mini_test.py). Air and Pro only develop and build.

Databases and the Monday 9 a.m. inspection are in [datasource-lab](../../../datasource-lab/SKILL.md). Slots and Console ports are in [mini-release](../../references/mini-release.md). Console sessions are in [cloudcanal-console-automation](../../../cloudcanal-console-automation/SKILL.md).
