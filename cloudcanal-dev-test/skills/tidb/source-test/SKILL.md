---
name: cloudcanal-tidb-source-test
description: Run and verify CloudCanal TiDB source CDC regression tests, including raw/comparable span correctness, DML/DDL ordering, TiKV CDC stream errors, DEADLINE_EXCEEDED retry, not_leader, epoch_not_match, partition table changes, checkpoint recovery, and log/metric validation. Use when a user asks to test, validate, regression-test, or produce a CloudCanal TiDB source CDC test report and can provide CloudCanal task logs, source TiDB credentials, target database credentials, and any needed manual task parameter changes.
---

# CloudCanal TiDB Source Test

## Purpose

Use this skill to run a disciplined CloudCanal TiDB source CDC regression pass. The test focus is correctness: no data loss, consistent region subscription state, correct DDL barriers, and clear recovery from stream/region errors.

## Required Inputs

Ask for these before running tests:

- CloudCanal task log machine: host, SSH user, password or key access.
- CloudCanal log paths: main task log, `apply_commit.log`, and optional check task `diff.log`.
- Source TiDB: host, SQL port, user, password, test database.
- Target database: host, SQL port, user, password, target database.
- PD endpoint for TiKV leader/split tests, for example `http://<pd-host>:2379`.
- Task creation/start time, if row-count differences may include pre-task seed data.
- Whether destructive DDL is allowed: `TRUNCATE TABLE`, `TRUNCATE PARTITION`, `DROP/ADD PARTITION`.
- Whether DEADLINE testing is enabled. This usually requires a human to edit CloudCanal task parameters such as `cdcStubTimeout` and possibly `fastFailKeywords`, then restart/redeploy the task.

Never hardcode passwords into skill files. Prefer environment variables for scripts.

## Workflow

1. Read [references/case-plan.md](references/case-plan.md) before choosing cases. It contains the 18-case plan and pass criteria.
2. Prepare a dedicated test database and make sure CloudCanal subscribes it before writing test rows.
3. Capture log offsets before each disruptive case so log verification only scans new output.
4. Run DML/DDL/error cases with unique marker prefixes.
5. Verify both data and logs. Data consistency is primary; logs explain state transitions.
6. Treat temporary `errRegionSize` or `uninitializedRegionSize` during resubscription as normal if the final metrics recover and post-recovery DML syncs.
7. Produce a final report with cases run, source/target counts, log evidence, and unresolved risks.

## Scripts

Use `scripts/tidb_cdc_db_tool.py` for database-side setup, marker writes, comparison, and the combined stress case.

Typical setup:

```bash
export CC_SRC_HOST=192.168.0.180
export CC_SRC_PORT=4000
export CC_SRC_USER=root
export CC_SRC_PASS=''
export CC_DST_HOST=127.0.0.1
export CC_DST_PORT=3306
export CC_DST_USER=root
export CC_DST_PASS='...'
export CC_TEST_DB=cc_tidb_cdc_test
```

Run the commands below from this skill directory.

Prepare source test schema:

```bash
python3 scripts/tidb_cdc_db_tool.py prepare-schema
```

Compare source and target table counts:

```bash
python3 scripts/tidb_cdc_db_tool.py counts
```

Insert a post-recovery probe and wait for target:

```bash
python3 scripts/tidb_cdc_db_tool.py post-probe --table cc_cdc_region_02
```

Run the combined disruptive case:

```bash
python3 scripts/tidb_cdc_db_tool.py combo-stress \
  --pd-url http://192.168.0.180:2379 \
  --evict-store-id 2 \
  --allow-truncate
```

Use `scripts/scan_cloudcanal_logs.sh` to scan local or remote logs. It supports SSH via `CC_LOG_HOST`, `CC_LOG_USER`, and optional `CC_LOG_PASS` if `sshpass` is installed.

```bash
export CC_MAIN_LOG=/path/to/<TASK>_INCREMENT.log
export CC_APPLY_LOG=/path/to/apply_commit.log
export CC_START_OFFSET=1
scripts/scan_cloudcanal_logs.sh
```

## Log Verification Rules

Good recovery patterns:

- `Region grpc error:...DEADLINE_EXCEEDED` followed by `Begin to re schedule region request,reason:grpc_error`, `Re schedule region request success`, and `Region is initialized`.
- `Region event error:not_leader` followed by `Begin to re schedule region request,reason:not_leader` and `Region is initialized`.
- `Region event error:epoch_not_match` or `region_not_found` followed by `Begin to re schedule range request` and new region initialization.
- DDL logs show `[DDL JOB]`, `[REAL DDL]`, `[REMOVE DDL JOB]`, then target DDL execution and later DML fetch.
- Final metrics return to `uninitializedRegionSize:0,errRegionSize:0` after the disruption window.

Bad signals:

- `Process event failed`
- `ErrPrewriteNotMatch`
- `CheckpointTs is greater than next ddl commitTs`
- `clusterIdMismatch`
- `duplicateRequest`
- `matched fastFailKeywords`
- `Try to exist with System.exit`
- Long-lived nonzero `errRegionSize` or `uninitializedRegionSize` without later recovery
- Target table marker counts lower than source

`SKIP_SPAN_...` can be normal when one TiKV region carries events for other table spans. It is a bug only if the subscribed table's own marker DML is skipped and missing on the target.

## Reporting

Report in Markdown with:

- Environment and task paths.
- Exact cases run.
- Marker prefixes and row counts.
- Log evidence: key patterns and whether final metrics recovered.
- Any manual parameter changes, especially `cdcStubTimeout` and `fastFailKeywords`.
- Known non-issues, such as seed rows created before task start.

When a source/target count differs, first check task creation time and apply log. A row that existed before the incremental task start is not a CDC loss.
