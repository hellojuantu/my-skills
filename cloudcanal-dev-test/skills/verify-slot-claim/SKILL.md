---
name: verify-slot-claim
description: "Check that a CloudCanal slot release with an older claimId cannot clear the claim that is there now. Use when editing slot_claim.py, change_claim, acquire_claim, slot_lock, or the slot claim model."
---

# 槽位预留的 claimId

一次释放只能归档它点名的那次预留。调用者拿着旧的 `claimId` 再释放时，当前占用必须还在。否则后一轮发布的预留会被前一轮清掉，接下来的替换和重启会打到别人的槽位上。

模型在 `model/SlotClaim.tla`。`owner` 是 `owner.json` 里的 `claimId`，`0` 表示预留目录不存在。`memory[p]` 是调用者还留着、可以再次提交的 id。`live` 不是代码，它记录“只被同一个 id 释放过”的那次预留。性质是 `OwnerIsLive`：`owner = live`。

`change_claim` 在 `slot_lock` 里读完再写，所以模型里的申请和释放各是一步。这一步对应同一技能里 `scripts/slot_claim.py` 的 `change_claim`、`acquire_claim` 和 `slot_lock`。

## 什么时候要重跑

改了 `slot_claim.py` 里的 `change_claim`、`acquire_claim`、`slot_lock` 或 `status` 的加锁方式就要重跑。只改文档、状态查询的输出字段，或和预留目录无关的参数时不用跑。

## 怎么跑

在 `my-skills` 仓库根目录：

```sh
python3 cloudcanal-dev-test/skills/verify-slot-claim/scripts/code_matches_model.py
```

脚本在临时目录运行。它用两个写者检查独占锁的互斥性，再用两个槽位检查 `status` 读每条记录时是否持续持有两把共享锁。申请、更新和释放时，脚本在读取预留、创建目录、替换 `owner.json` 和归档目录时分别核对所持的锁。每次操作从读到写都必须持有同一次取得的槽位独占锁。脚本也会验证重复申请和用不同 `claimId` 释放都保留原预留。任一检查失败时退出码为 1。`access` 记录验证任务或替换 JAR 的用途。

然后用 `/statechart` 读 `cloudcanal-dev-test/skills/verify-slot-claim/model/SlotClaim.tla` 的结果。通过配置是旁边的 `SlotClaim.cfg`（`CheckIds = TRUE`）。图表用词在同目录的 `view.mjs`。`/statechart` 的命令和路径以那份技能当时的说明为准，这里不抄。

`cloudcanal-dev-test/skills/verify-slot-claim/model/Broken.cfg` 把 `CheckIds` 设为 `FALSE`，也就是删掉释放前的 `claimId` 比较。这组配置必须失败。失败路径是：调用者 A 申请并释放，调用者 B 申请，A 再用自己留下的旧 id 释放，当前占用被清掉。当前代码要保持在通过的那一组。

## 失败时怎么看

先分清是代码坏了，还是模型跟代码脱节。

- `code_matches_model.py` 失败：锁没有互斥，已有预留被再次申请换掉，或另一个 `claimId` 释放了当前预留。这是代码和模型不一致。用 `/statechart` 跑 `Broken.cfg` 可以看见旧 id 清掉当前占用的最短路径。在确认现有代码就该如此之前，不要改性质，也不要改模型去迎合它。
- 源码检查通过，但 `SlotClaim.cfg` 失败：模型或性质和代码的锁内步骤对不上。对照 `change_claim` 里同一次加锁中的读写，修正模型里多出来或少掉的那一步，再重跑。不要为了通过去放宽 `OwnerIsLive`。
- 只有 `Broken.cfg` 失败：检查本身还能抓住这个错误。

## 范围

两个调用者，一个槽位，最多 3 个 claim id。锁把同一个槽位上的申请、更新和释放串成完整的一步。更新只保留同一个 `claimId`，不改 id。

`status` 按槽号顺序取得本次查询涉及的所有共享锁，再读取各条记录。这样，`allRegisteredClaimed` 和每个已登记槽位的占用来自同一次快照。多槽位查询由 Python 对照器检查。TLA 模型只覆盖单槽位上的并发操作。创建目录后进程中断、旧文本预留和 `confirmed-ended`、归档重名、槽位登记和 Mini 远程转发均在模型范围之外。

## 与代码同步

上次对照的是工作区里尚未提交的 `slot_claim.py`，仓库提交是 `b75065cdf7123f12e62394f7ee3eb5d6d9b6803e`。该提交里没有这份脚本。

只有重新读过当前 `change_claim`，确认模型仍描述同一次加锁里的申请和释放，并且 `SlotClaim.cfg` 通过、`Broken.cfg` 失败之后，才把这里的提交号改成新的提交。代码在这次确认之后又改过，就先重跑，再决定模型要不要跟着改。之后若还有没经过这次检查的改动，用 `/maintain-formal-verification-skill` 把模型和代码对齐。
