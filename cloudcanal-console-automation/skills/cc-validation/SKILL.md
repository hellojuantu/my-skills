---
name: cc-validation
description: Check CloudCanal automation results and clean up temporary objects only when the user asks. Use for acceptance and cleanup, not for creating jobs.
---

# Validation checklist

Before you hand work to someone else:

1. Run `python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" doctor`.
2. Set `CC_BASE_URL`, `CC_COOKIE_FILE`, and optionally `CC_CLUSTER_ID` in the shell. Do not put them in the skill files.
3. Do not commit cookies, generated payloads that contain passwords, datasource reports, or local absolute paths.
4. For Automation login, set `SM_CRYPTO_NODE_MODULE_DIR` or `CLOUDCANAL_WEB_DIR` if the command cannot find `sm-crypto`. Reuse the existing session for later commands.
5. Run the frontend parity audit for the target `clouddm-web` checkout. Note which workflows are named commands and which still use `call-service`.
6. Run `python3 "$CLOUDCANAL_SKILL/scripts/audit_frontend_datasource_types.py" --frontend-dir "$CLOUDCANAL_WEB_DIR"`. Check whether the Console CLI recognizes the types the job uses.

Before a live write:

1. Confirm `CC_BASE_URL`, the cookie, and the cluster id.
2. Run `clusters` when the user only gives an environment URL.
3. Use `--dry-run` for create, edit, update, position, and schedule commands.
4. Query dynamic kv and job extra configs for an unfamiliar datasource type or pair.
5. Query the saved datasource runtime config with `query-ds-config` for a special source or target.
6. Compare a special source-target pair with frontend behavior before you claim parity.

After you create or update a datasource:

1. Run `test` with the final datasource id and cluster id.
2. Query or list the datasource when the user needs ids or names.

After you create or edit a job:

1. Query the job with `query-job`.
2. Query schema and mapping with `query-job-schema`.
3. Run precheck unless the user skips it on purpose.
4. When creation is async, wait for or query the console job before start.
5. Start only when asked, or when `--start-after-create` is part of the plan.
6. Do not delete a temporary test job unless the user asks for cleanup.

For a CloudCanal change, use [API acceptance](../../../cloudcanal-dev-test/references/api-job.md). Record the Console origin, actual API response, job ID, saved config, state, and native target readback. Use pages and screenshots only when the user explicitly requests page operation.

Report the environment URL and cluster id. Report datasource ids or job ids you created. Report the connection or precheck result, the job state, and any consistency check you were asked to run. When an async step fails, report the console job id and the failed step. Report cleanup you took. Name any branch that was only dry-run verified.

## Cleanup only when requested by the user

Confirm the exact datasource or job IDs and their test-run ownership. Include child jobs only when they are part of the confirmed scope.

Delete temporary datasources with `delete --yes` after connection tests.

Delete temporary jobs with `delete-job --delete-children --stop-first --inactivate-fsm` after precheck, start, or operation tests. Do this so an active check-child FSM does not force a manual Console cleanup.

Keep only reusable examples in the skill. Store one-off test output outside the skill. Or remove it before you share the skill.
