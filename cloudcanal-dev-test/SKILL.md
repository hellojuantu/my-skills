---
name: cloudcanal-dev-test
description: Develop and build CloudCanal on Air or Pro, run tests on Mini, and accept them on the real Console. Create a job on the existing version directly, and use a separate slot when you need to deploy. Also use this for CloudCanal coding rules, reverse-merging dev, and the manual QA note.
---

# Develop CloudCanal and accept it on Mini

Write and build on Air or Pro. Run unit tests, frontend tests, component tests, JDBC programs, and test services on Mini.

Create, configure, run, and accept a test with [Console API automation](../cloudcanal-console-automation/SKILL.md). Open a browser only when the user asks to see the page.

Prefer a test database that is already registered on Mini. Do not create a backup unless the user asks. When the user asks for a backup, follow [Backups](references/backups.md). When no registered instance fits, install one and register it with [Manual install on Mini](../datasource-lab/SKILL.md#manual-install-on-mini).

When you only create or view a job on the existing version, call the matching Mini Console API directly. Only when you load this round's code, replace a JAR, or restart a service, follow [Slot release](references/mini-release.md).

Before the test, put this round's source, patch, or artifacts in a separate directory on Mini. Run this from the development machine:

```sh
python3 scripts/run_mini_test.py --workdir '<Mini directory>' -- <command> <arguments>
```

The work directory and the command both run on Mini. The receipt names the host and the exit code. A component test can also run `docker exec` on Mini through this entry.

## Work through one change

Run the change in this order.

1. Write the scope first. Create or switch a task branch only in a repository that this change touches. Leave an unchanged repository on its current branch. When you build a dependency, use a separate checkout at the specified SHA. Do not move an unchanged repository onto a branch of the same name.

   Record the normal entry, the smallest reproduction, and a result you can observe. In that same note, include the repositories, the source, the target, and the job type. For each repository, include the branch, the full HEAD, and the files in this patch. When the workspace still has someone else's changes, make another checkout from the recorded HEAD. Take this round's changes with `git diff --binary HEAD`. Find new files to copy with `git ls-files --others --exclude-standard`.
2. Change the code next. Follow [coding workflow](references/coding-workflow.md) for the code, the commit, and the QA note. Before a Poteto flow, read [Codex agents](skills/cc-setup/SKILL.md#codex-agents). For a small change, reproduce it, then edit the step that fails. When you change shared logic, read the callers.

   The original flows are listed in the [pstack index](references/pstack-index.md). When the user asks you to work with Claude, read the [Claude handoff](references/claude-collaboration.md).
3. Build and test next. On the development machine, only build. For example, use Gradle `assemble`, or Maven `-Dmaven.test.skip=true package`. After a workspace dependency version changes, fill the Maven Local that IDEA uses. Follow [IDEA local dependencies](references/idea-dependencies.md). A successful isolated build does not mean that repository is ready. Run unit tests and engine component tests through the Mini entry above. When the change touches JDBC, read and write once with the real driver.

   When you need to deploy, take one empty slot alone. Follow [Slot release](references/mini-release.md). When every slot is taken, list the holders. Wait until the user has read the sessions and decided. When the slot has no test database, add one from [Datasource lab](../datasource-lab/SKILL.md).
4. Accept through the Mini Console API. When the change includes a datasource or a driver, run the [CloudCanal slot connection check](../datasource-lab/SKILL.md#cloudcanal-slot-connection-check). Write each Worker connection into the [Mini CHECK report](../datasource-lab/references/check-report.md).

   For a data job, save the request source, the job ID, and the status with [API evidence](references/api-job.md). Then read the data back from the target. Prepare the config and the queries with [Console automation](../cloudcanal-console-automation/SKILL.md).

   Use the Automation login session for that same slot. When the API response itself asks for an identity check that a person must finish, report the original prompt. When SSH asks for a Tailscale check, open the link as [Mini SSH identity check](skills/cc-setup/SKILL.md#mini-ssh-identity-check) describes.

   When an API call fails, record the API, the job ID, the raw error, and the step that did not finish. When the user asks for a page action, save the page evidence as [Page evidence](references/browser-job.md) describes.
5. Close the round. Stop the incremental job this round created for acceptance. Follow [Stop a new incremental acceptance job](references/browser-job.md#stop-a-new-incremental-acceptance-job). In the delivery, write the Mini Console entry, the job ID, the API result, and the target read-back. When you deployed, attach each repository SHA, the slot, and the checksum of each loaded JAR.

## Acceptance rules and checks

Test processes run on Mini. `scripts/run_mini_test.py` confirms the host over SSH, runs the command, and reads the exit code.

On the existing version, create or view a job directly in the Mini Console. Record the real URL and the job ID. When you deploy a new version, take a slot alone.

See the slots and the holders with `scripts/slot_claim.py status`. After you claim a slot, record the `claimId`. When the test is done, keep that write claim and set it to `awaiting-handoff`. Release the claim only when the user explicitly asks.

When every slot is taken, list the occupied sessions for the user to choose. When you start a job, do not look up claims. When you change the lock or the release path in `slot_claim.py`, rerun [verify-slot-claim](skills/verify-slot-claim/SKILL.md).

Mini Automation gets this slot's session with its own `login --save-cookie`. When the user explicitly asks for a page action, use the browser that is already logged in on this slot. When login or an identity check must be handed over, keep the prompt from the page.

Compare full and incremental results on the same input, row by row. When you compare versions, keep the same evidence for each version. For a timestamp read-back, follow [Compare full and incremental rows](references/browser-job.md#compare-full-and-incremental-rows). `phase-readback` checks the values in one run and checks that the two phases agree in another.

A Console end-to-end result includes this round's job ID. For a component test, name the read stage and the write stage it actually reached.

By default, `api-job` checks API creation, the job, and the start status. Use `browser-job` for screenshots and the page source only when the user asks for the page. `fresh-check` checks the finish time of this round's CHECK subtask.

When you close incremental acceptance, stop the job this round created and started. When the user asks to keep it running, record the status. `stopped-test-job` checks the receipt for that same job after the stop. Confirm that `fsmActive=false` and that the incremental subtask is `STOP`.

## Check a data path

Query the real source, the real target, and the Worker cluster through the Console API. Select them from that result. Check the connection, the subscribed objects, and the key parameters. After you save, read the config and the mapping back through the API. After you start, query that same job and its subtask status.

When the case says to create the target objects automatically, check the options the API saved. Then use the target engine's own entry to confirm that the objects exist.

Check the full phase against the sample you prepared. For the incremental phase, confirm from the engine status or the log that this job's reader is ready. Write one change that carries a unique marker. Read that change back through the target's own entry.

Compare full and incremental results with the same business values. When you check a restart, a resume, or a config comparison, record the version and the data separately for each round.

When the path supports CHECK and the case requires it, create a separate CHECK, or rerun CHECK from a finished job. Save the API result and this round's job snapshot. Use `scripts/check_console_jobs.py fresh-check` to check the finish time, the job ID, and that the run belongs to this round. Judge the result from the target read-back together with the CHECK row count, the difference count, and the missing-row count.
