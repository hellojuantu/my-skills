---
name: verify-slot-claim
description: "Check that a CloudCanal slot release with an older claimId cannot clear the claim that is there now. Use when editing slot_claim.py, change_claim, acquire_claim, slot_lock, or the slot claim model."
---

# Slot reservation claimId

A release archives only the reservation written in the request. When a caller releases again with an old `claimId`, the current occupancy must still be there. Otherwise an earlier round clears the later reservation. The replace and restart that follow land on someone else's slot.

The model is `model/SlotClaim.tla`. `owner` is the `claimId` in `owner.json`. `0` means the reservation directory does not exist. `memory[p]` is an id the caller still holds and can submit again.

`live` is not code. It records the reservation that has been released only by that same id. The property is `OwnerIsLive`. It is `owner = live`.

`change_claim` reads and then writes inside `slot_lock`, so acquire and release are each one step in the model. That step matches `change_claim`, `acquire_claim`, and `slot_lock` in this skill's `scripts/slot_claim.py`.

## When to rerun

Rerun after a change to `change_claim`, `acquire_claim`, or `slot_lock` in `slot_claim.py`, or to the way `status` takes its locks. Skip the run when the change is only documentation, status-query output fields, or parameters that do not touch the reservation directory.

## How to run

From the `my-skills` repository root, run this.

```sh
python3 cloudcanal-dev-test/skills/verify-slot-claim/scripts/code_matches_model.py
```

The script runs in a temporary directory. It uses two writers to check that the exclusive lock is mutually exclusive. It uses two slots to check that `status` holds both shared locks the whole time it reads each record.

On acquire, update, and release, the script checks the lock it holds while reading the reservation, creating the directory, replacing `owner.json`, and archiving the directory. From the read through the write, it must hold the slot exclusive lock from that same acquisition. A repeated acquire, and a release with a different `claimId`, must leave the original reservation. The exit code is 1 when any check fails. `access` records whether this run is a verification task or a JAR replacement.

Then use `/statechart` to read the result for `cloudcanal-dev-test/skills/verify-slot-claim/model/SlotClaim.tla`. The passing config is the neighboring `SlotClaim.cfg`, where `CheckIds = TRUE`. The chart wording is in `view.mjs` in the same directory. Use the `/statechart` command and paths from that skill's instructions at the time. Do not copy them here.

`Broken.cfg` sets `CheckIds` to `FALSE`. That removes the `claimId` comparison before release. This config must fail. The failing path runs as follows. Caller A acquires and releases. Caller B acquires. A releases again with the old id it kept. That release clears the current occupancy. The current code must stay on the config that passes.

## How to read a failure

First distinguish whether the code is broken or the model has drifted from the code. When `code_matches_model.py` fails, the lock is not mutually exclusive, an existing reservation was replaced by another acquire, or another `claimId` released the current reservation. The code and the model disagree. Run `Broken.cfg` with `/statechart` to see the shortest path where an old id clears the current occupancy. Do not change the property until you confirm the current code should behave this way. Do not change the model to match it before that confirmation.

When the source check passes but `SlotClaim.cfg` fails, the model or the property does not match the steps inside the code's lock. Compare the reads and writes inside the same lock in `change_claim`. Fix the extra or missing step in the model, then rerun. Do not relax `OwnerIsLive` in order to pass.

When only `Broken.cfg` fails, the check can still catch this mistake.

## Scope

Two callers, one slot, and at most 3 claim ids. The lock turns acquire, update, and release on the same slot into one complete step. An update keeps the same `claimId` and does not change the id.

`status` takes every shared lock this query uses, in slot-number order, and then reads each record. `allRegisteredClaimed` and the occupancy of each registered slot then come from the same snapshot.

Multi-slot queries are checked by the Python checker. The TLA model covers only concurrent operations on a single slot.

A process interrupted after it creates the directory, an old text reservation, the user's release authorization, an archive name collision, slot registration, and Mini remote forwarding are outside the model.

## In sync with the code

The `slot_claim.py` Git blob compared on Mini this time is `0427f5f86a486d92054f2765c38f0274b853325a`. `code_matches_model.py` passed. TLC checked 25 distinct states of `SlotClaim.cfg`, and every state satisfies `OwnerIsLive`. State 5 of `Broken.cfg` reproduced an old id clearing a new reservation.

Update the source version recorded here only after you reread the current `change_claim`, confirm that the model still describes acquire and release inside the same lock, and see `SlotClaim.cfg` pass and `Broken.cfg` fail. If the code changes after that confirmation, rerun first. Then decide whether the model should follow. If a later change has not been through this check, use `/maintain-formal-verification-skill` to align the model with the code.
