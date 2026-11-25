---
name: cloudcanal-console-automation
description: Drive CloudCanal Console through its login session and frontend APIs. Use it to manage and test datasources, create data jobs, change subscriptions or job config, start, stop, or rerun jobs, and adjust schedules or positions.
---

# CloudCanal console automation

## Follow the Console frontend

Use the Console frontend APIs. Before an unverified datasource pair, check the real frontend request, the dynamic WebOp, or the generated body. Build parameters from the levels, mappings, and connection settings that engine actually supports.

Page acceptance for a CloudCanal change follows [CloudCanal dev test](../cloudcanal-dev-test/SKILL.md).

Run scripts from this skill directory.

For an isolated Mini checkout, keep the adjacent `cloudcanal-dev-test` skill available. Automation loads its `scripts/mini_names.py` to validate the Console origin.

```bash
export CLOUDCANAL_SKILL="${CLOUDCANAL_SKILL:-$PWD}"
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" --help
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" doctor
```

Login encrypts the password with `sm-crypto`. Point `SM_CRYPTO_NODE_MODULE_DIR` at the `node_modules` that contains it. The scripts also search upward from the working directory and read `CLOUDCANAL_WEB_DIR` or `CLOUDCANAL_REAKH_DIR`.

On Mini, take the Console hostname from `mini.env` and the port from [slot registration](../cloudcanal-dev-test/references/mini-release.md). Reuse the Automation session for that exact origin. When the session file is missing, run `login --base-url "$CC_BASE_URL" --save-cookie "$CC_COOKIE_FILE"` and pass `--cookie-file "$CC_COOKIE_FILE"` on later commands. An authorized CLI login reads `--account` and `--password`, then `CC_ACCOUNT` and `CC_PASSWORD`, then an interactive prompt. Hand a Console login page, SSO, or identity check to the user. Keep credentials and session files outside the repo. Session files are mode `0600`.

On first setup, run `doctor` to check Python, Node, `sm-crypto`, an optional `clouddm-web` workspace, the session, and the Console address. Add `--check-api` to query the default cluster.

## Procedure

1. Confirm the Console address, the slot session, and the Worker cluster. Pass `--base-url`, `--cookie-file`, and `--cluster-id` when it applies.
2. Before a write, load the dynamic definitions for that operation, such as datasource KV, extra job config, mapping rules, and the WebOp position form.
3. Before create, edit, update, position change, or schedule change, check the request with `--dry-run`.
4. In a test environment, write temporary jobs and datasources first. After the user authorizes cleanup, follow [cleanup](skills/cc-validation/SKILL.md#cleanup-only-when-requested-by-the-user).
5. After create or edit, read the saved object back. Run a connection test on its own when the datasource connection must be checked.
6. After a structure, full, and increment job is created, check its state. When structure is finished, `fsmActive=false`, and the following task is still `INIT`, run `continue-job` so the frontend `fsmStart` path runs.

Prefer Lab-registered databases for Mini link tests. When a new instance is required, prepare it with [Datasource Lab](../datasource-lab/SKILL.md), then register it and operate the job from this skill. Record read-only inspection results in the [Mini CHECK report](../datasource-lab/references/check-report.md). Apply the authorized scope and use the report to confirm any cleanup.

Creating a job copies datasource connection fields and dedicated config. An existing job keeps the values saved at creation. To repair a failed job, read the fields with `list-job-configs`, check `endPointType` and `configType`, fix the affected `SOURCE` or `TARGET` `DATASOURCE` config with `update-job-configs`, then retry the failed async operation with `operate-console-job --action retry`. If the sample was built against the old address, rebuild the test data or the job before verifying again.

When the frontend API has no dedicated subcommand, confirm the service key with `list-services`, then check the request with `call-service --service ... --payload-json @file --dry-run`. When only a raw path is known, use `call-api --path ...`. Add a dedicated command after the same flow is reused often.

## References

- [Create, update, delete, and test datasources](skills/cc-datasource/SKILL.md)
- [Create jobs and change subscriptions](skills/cc-datajob/SKILL.md)
- [Job actions, config, schedule, and position](skills/cc-job-operations/SKILL.md)
- [Frontend requests and engine-specific cases](skills/cc-frontend-parity/SKILL.md)
- [Acceptance and cleanup](skills/cc-validation/SKILL.md)

## What to report

Report the datasources, pairs, and stages that were actually verified. When a frontend request or a `--dry-run` comparison is still missing, name it in the result.
