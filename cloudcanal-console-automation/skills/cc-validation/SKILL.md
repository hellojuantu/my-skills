---
name: cc-validation
description: Check CloudCanal automation results and clean up temporary objects only when the user asks. Use for acceptance and cleanup, not for creating jobs.
---

# Validation Checklist

Before teammate handoff:

1. Run `python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" doctor`.
2. Run `python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-selftest` to verify the offline full/increment/check/faker orchestration.
3. Set `CC_BASE_URL`, `CC_COOKIE_FILE`, and optionally `CC_CLUSTER_ID` in the shell, not inside the skill files.
4. Do not commit cookies, generated payloads containing passwords, datasource reports, or local absolute paths.
5. For Automation login, set `SM_CRYPTO_NODE_MODULE_DIR` or `CLOUDCANAL_WEB_DIR` if the command cannot locate `sm-crypto`. Reuse the existing session for subsequent commands.
6. Run the frontend parity audit for the target `clouddm-web` checkout and note which workflows are named commands versus `call-service` fallback.
7. Run `python3 "$CLOUDCANAL_SKILL/scripts/audit_frontend_datasource_types.py" --frontend-dir "$CLOUDCANAL_WEB_DIR"` and confirm no frontend datasource type is missing from adapter routing.
8. For autotest work, run `autotest-deps`, `autotest-plan`, and `autotest-matrix --summary-only` before live writes.

Before live writes:

1. Confirm `CC_BASE_URL`, cookie, and cluster id.
2. Run `clusters` if the user only gives an environment URL.
3. Use `--dry-run` for create/edit/update/position/schedule commands.
4. Query dynamic kv/job extra configs for unfamiliar datasource types or pairs.
5. Query saved datasource runtime config with `query-ds-config` for special sources or targets.
6. Compare special source-target pairs against frontend behavior before claiming parity.

After datasource create/update:

1. Run `test` with the final datasource id and cluster id.
2. Query/list the datasource if the user needs ids or names.

After job create/edit:

1. Query the job with `query-job`.
2. Query schema/mapping with `query-job-schema`.
3. Run precheck unless the user intentionally skips it.
4. If creation is async, wait for or query the console job before start.
5. Start only when requested or when `--start-after-create` is part of the plan.
6. Do not delete temporary test jobs unless the user explicitly asks for cleanup.

Before N*N autotest:

1. Generate the matrix with `autotest-matrix --batch-size 5`.
2. Use schemas/databases prefixed with `cc_auto_`; adapter commands refuse non-temp schemas unless explicitly overridden.
3. Apply user scoping such as `--desc-prefix codex-` before selecting pairs.
4. Run the first batch in `--dry-run` mode and inspect that one job contains all profile tables.
5. For datasource families without implemented faker/check behavior, record them as adapter-routed but not data-verified. Do not include them in a normal N*N ready batch unless the user explicitly asks for `--include-unready`.
6. Save run JSON and reports outside the skill directory.
7. Do not automatically clean temporary datasets or jobs; report what was created and wait for the user to ask for deletion.

Before marking a new non-RDB datasource family `READY`, verify all four operations against the real system: create/init temporary objects, generate source changes, local count or digest snapshot, and cleanup. If the only available validation is a CloudCanal check child or a frontend-specific endpoint, document that alternative and keep local-data capabilities false.

Report:

- Environment URL and cluster id used.
- Datasource ids or job ids created.
- Connection/precheck result.
- Phase-level pair state, such as create ok, start failed, faker error, verify failed, or check child failed.
- Console job id and failed async step when present.
- Cleanup actions taken.
- Any branch that was only dry-run verified, not live-created.

## Cleanup only when requested by the user

- Delete temporary datasources with `delete --yes` after connection tests.
- Delete temporary jobs with `delete-job --delete-children --stop-first --inactivate-fsm` after precheck/start/operation tests, so active check-child FSMs do not force a manual Console cleanup.
- Keep only reusable examples in the skill; store one-off test outputs outside the skill or remove them before sharing.
