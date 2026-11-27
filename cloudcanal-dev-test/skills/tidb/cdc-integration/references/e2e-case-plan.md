# CloudCanal TiDB CDC End-to-End Case Plan

## Contents

1. [Pass definition](#pass-definition)
2. [Required topology](#required-topology)
3. [Environment and task setup](#environment-and-task-setup)
4. [Evidence protocol](#evidence-protocol)
5. [Cases 1-6: region and transaction paths](#cases-1-6-region-and-transaction-paths)
6. [Cases 7-12: DML, DDL, partition, and case sensitivity](#cases-7-12-dml-ddl-partition-and-case-sensitivity)
7. [Cases 13-18: recovery, load, restart, GC, and observability](#cases-13-18-recovery-load-restart-gc-and-observability)
8. [Combined stress](#combined-stress)
9. [Cleanup and report](#cleanup-and-report)

## Pass definition

A case passes only when all applicable evidence exists:

1. The intended branch or fault actually occurred.
2. The main log shows the expected error followed by reschedule and re-initialization in order.
3. Source and target marker counts and critical values match the documented final state.
4. The case log window contains no fatal marker.
5. A new post-case DML probe reaches the target.
6. Final metrics return to `uninitializedRegionSize:0,errRegionSize:0` for fault cases.

Use these statuses exactly:

- `PASS`: all required evidence exists.
- `FAIL`: the case ran and violated data, recovery, or fatal-log criteria.
- `BLOCKED`: required access, topology, or authorization is unavailable.
- `NOT TRIGGERED`: injection ran but the expected TiKV/CDC branch did not occur.
- `NOT RUN`: no attempt was made.

Any status other than PASS prevents an “18/18 complete suite passed” conclusion.

## Required topology

| Capability                    | Minimum environment                                                          | Cases                   |
|-------------------------------|------------------------------------------------------------------------------|-------------------------|
| Direct decoder                | 1 TiDB, 1 PD, 1 TiKV                                                         | Layer B only            |
| Ordinary source-to-target CDC | CloudCanal task + source + separate target                                   | 1, 5-12, 14, 15, 17, 18 |
| Region split epoch transition | 1 TiKV can trigger it, but verify the log                                    | 2                       |
| Leader migration              | 3 TiKV replicas                                                              | 3                       |
| Deadline recovery             | Mutable `cdcStubTimeout` and `fastFailKeywords`, or controlled network fault | 4                       |
| Region disappearance          | Disposable multi-TiKV cluster with controlled merge                          | 13                      |
| Parallel ownership            | Actual CloudCanal task with `allParallel > 1` and enough worker slots        | 16                      |
| Combined stress               | 3 TiKV, mutable task config, destructive opt-in                              | combined                |

A same-host 3-TiKV playground validates state transitions, not physical-machine resilience. Do not claim host-failure or
long-term stability without a multi-host cluster.

Start a disposable state-transition topology with:

```bash
tiup playground v7.5.7 \
  --tag cc-tidb-cdc-chaos-it \
  --db 2 \
  --pd 3 \
  --kv 3 \
  --tiflash 0
```

Read actual endpoints from TiUP output. Stop with `Ctrl+C`; after evidence is retained, use `tiup status` and
`tiup clean <exact-name>`. Never clean all instances on a shared host.

## Environment and task setup

### Variables

```bash
export CC_SRC_HOST='<tidb-sql-host>'
export CC_SRC_PORT='<tidb-sql-port>'
export CC_SRC_USER='<source-user>'
# Inject CC_SRC_PASS securely.
export CC_PD_URL='http://<pd-host>:<pd-port>'

export CC_DST_HOST='<target-host>'
export CC_DST_PORT='<target-port>'
export CC_DST_USER='<target-user>'
# Inject CC_DST_PASS securely.
export CC_TEST_DB='cc_tidb_cdc_test'

export CC_TASK_ID='<cloudcanal-task-id>'
export CC_MAIN_LOG='/home/clougence/logs/cloudcanal/tasks/<task>_INCREMENT/<task>_INCREMENT.log'
export CC_APPLY_LOG='/home/clougence/logs/cloudcanal/tasks/<task>_INCREMENT/apply_commit.log'
export CC_RUN_ID="ai_$(date -u +%Y%m%dT%H%M%SZ)"
```

Source and target must be different dedicated databases. Verify SQL, PD, every TiKV advertised address, target,
CloudCanal worker, and log-host access.

The bundled schema intentionally fixes the source database name to `cc_tidb_cdc_test`. Require
`CC_TEST_DB=cc_tidb_cdc_test`; do not pretend another value was applied without first creating a run-specific copy of
the SQL and recording that change.

### Destructive opt-in

Before any fault/DDL/truncate operation:

```bash
export ALLOW_DESTRUCTIVE=true
test "$ALLOW_DESTRUCTIVE" = true
```

Record current values for every task/PD setting that a case will change. Prepare a cleanup command before injection.

### Source schema

Before creating or starting the CloudCanal task, apply the bundled schema:

```bash
MYSQL_PWD="$CC_SRC_PASS" mysql \
  -h "$CC_SRC_HOST" -P "$CC_SRC_PORT" -u "$CC_SRC_USER" \
  < "$HOME/.codex/skills/cloudcanal-dev-test/skills/tidb/cdc-integration/scripts/tidb-cdc-integration-schema.sql"
```

The script drops and recreates these seven tables in `cc_tidb_cdc_test`:

- `cc_cdc_dml_main`
- `cc_cdc_region_01`
- `cc_cdc_region_02`
- `cc_cdc_region_03`
- `cc_cdc_txn_conflict`
- `cc_cdc_partition_main`
- `cc_CDC_MixedCase`

It intentionally inserts no rows. Do not run it after the test task starts.

### CloudCanal task

1. Create a new full+increment task from the prepared source to a dedicated target.
2. Subscribe all seven tables and enable DDL synchronization.
3. Record CloudCanal version, TiDB version, task parameters, topology, task id, creation/start time, and worker host.
4. Wait for full sync completion, `Puller is initialized`, resolvedTs/checkpoint progress, and a clean source-target
   baseline.
5. For a pure incremental task, pre-create compatible target tables and clearly state that pre-task rows are outside the
   incremental contract.

## Evidence protocol

At the start of every case, use a unique marker prefix and record byte offsets:

```bash
export CC_CASE='c01'
export CC_MARKER="${CC_RUN_ID}_${CC_CASE}"
export CC_MAIN_OFFSET=$(( $(wc -c < "$CC_MAIN_LOG") + 1 ))
export CC_APPLY_OFFSET=$(( $(wc -c < "$CC_APPLY_LOG") + 1 ))
```

After injection:

1. Query source and target by the exact marker, not total-table count alone.
2. Compare row counts and every field modified by the case.
3. Save only the new log window:

```bash
tail -c +"$CC_MAIN_OFFSET" "$CC_MAIN_LOG" > "/tmp/${CC_RUN_ID}_${CC_CASE}_main.log"
tail -c +"$CC_APPLY_OFFSET" "$CC_APPLY_LOG" > "/tmp/${CC_RUN_ID}_${CC_CASE}_apply.log"
```

4. Scan recovery and fatal patterns:

```bash
rg -n 'epoch_not_match|not_leader|region_not_found|DEADLINE_EXCEEDED|Begin to re schedule|Re schedule region request success|Region is initialized|Puller is initialized|Receive DDL|\[DDL JOB\]|\[REAL DDL\]|notifyTableIdChanged|Updated GC SafePoint|uninitializedRegionSize|errRegionSize' \
  "/tmp/${CC_RUN_ID}_${CC_CASE}_main.log"

rg -n 'Process event failed|matched fastFailKeywords|System\.exit|Offer event into store failed|ErrPrewriteNotMatch|Decode fails,value length is zero|RocksDBException' \
  "/tmp/${CC_RUN_ID}_${CC_CASE}_main.log" \
  "/tmp/${CC_RUN_ID}_${CC_CASE}_apply.log"
```

No fatal match is necessary but not sufficient. Data and recovery evidence remain mandatory.

## Cases 1-6: region and transaction paths

### Case 1: multi-table same-region span

Goal: verify raw span/comparable request conversion does not lose one table when a region covers multiple table ranges.

1. Confirm through PD/region inspection that at least one region covers adjacent ranges for `cc_cdc_region_01/02/03`.
   Consecutive table creation improves but does not guarantee this layout.
2. Insert 100 rows per table using `<marker>_r01_*`, `_r02_*`, and `_r03_*`.
3. Wait for all three target marker counts to reach 100.

Pass: all three exact counts and values match; the log fetches subscribed-table rows. `SKIP_SPAN_` for another table is
acceptable.

### Case 2: `epoch_not_match` after split

Insert 20 pre-split rows, execute:

```sql
SPLIT TABLE
`cc_tidb_cdc_test
`.
`cc_cdc_region_01
`
BETWEEN (0) AND (1000000) REGIONS 16;
```

Then insert 20 post-split rows.

Pass: source and target both contain all 40 markers; the case log contains `epoch_not_match`, range reschedule, and
later initialized. If the error branch does not appear, mark NOT TRIGGERED even when data matches.

Retry at most three recorded split attempts, increasing the requested region count (16, 32, then 64) and writing a new
marker window each time. If none triggers the branch, stop as NOT TRIGGERED instead of looping indefinitely.

### Case 3: `not_leader` after leader eviction

List stores and select one currently leading subscribed regions:

```bash
tiup ctl:v7.5.7 pd -u "$CC_PD_URL" store
tiup ctl:v7.5.7 pd -u "$CC_PD_URL" scheduler add evict-leader-scheduler <store-id>
```

Continuously write markers for at least eight seconds, then always remove the scheduler:

```bash
tiup ctl:v7.5.7 pd -u "$CC_PD_URL" scheduler remove evict-leader-scheduler-<store-id>
```

Pass: `not_leader` and subsequent initialization appear in order; every fault-window marker matches. If cleanup fails,
report it prominently and do not leave the scheduler installed.

### Case 4: `DEADLINE_EXCEEDED`

1. Save the original `cdcStubTimeout` and `fastFailKeywords` (current defaults are 28,800,000 ms and
   `DEADLINE_EXCEEDED`).
2. Set `cdcStubTimeout=3000` on the disposable task.
3. Set `fastFailKeywords` to empty so this case validates retry rather than configured process fast-fail.
4. Restart the task and continuously write markers until the deadline appears.
5. Restore both original settings after the case.

Pass: the log contains `DEADLINE_EXCEEDED`, `reason:grpc_error`, reschedule success, and initialized; a post-deadline
marker reaches the target. If the keyword remains fatal, process termination is configuration behavior, not retry PASS.

### Case 5: PREWRITE + COMMIT

After task initialization, seed and update a row in one SQL session:

```sql
INSERT INTO cc_tidb_cdc_test.cc_cdc_txn_conflict
    (id, uid, count_value, remark)
VALUES (5001, 1, 0, '<marker>_seed');

SET tidb_enable_async_commit = 0;
SET tidb_enable_1pc = 0;
BEGIN
    OPTIMISTIC;
    UPDATE cc_tidb_cdc_test.cc_cdc_txn_conflict
    SET count_value = count_value + 1,
        remark      = '<marker>_commit'
    WHERE id = 5001;
    COMMIT;
```

Pass: target final value matches source and no `ErrPrewriteNotMatch` appears.

### Case 6: rollback/write conflict

Insert an independent row with id 6001 and this case's seed marker. Use two persistent SQL sessions. In both, disable
async commit and 1PC, start `BEGIN OPTIMISTIC`, and update row 6001 to different markers. Commit session B first;
session A must fail on commit or explicitly roll back.

Pass: target contains only the successful transaction's value; the failed marker never applies; no delayed
`ErrPrewriteNotMatch` appears after a cooldown.

## Cases 7-12: DML, DDL, partition, and case sensitivity

### Case 7: ordinary committed INSERT/UPDATE/DELETE

Perform one ordinary insert, wait for target, update all relevant fields, wait again, then delete and wait for absence.

Pass: both sides agree after every phase; delete emits no `Decode fails,value length is zero`.

### Case 8: TRUNCATE/tableId replacement

Seed old markers, wait for target, then:

```sql
TRUNCATE TABLE cc_tidb_cdc_test.cc_cdc_region_03;
INSERT INTO cc_tidb_cdc_test.cc_cdc_region_03
    (id, username, email, profile)
VALUES (8001, '<marker>_after', '<marker>_after@test', 'after_truncate');
```

Pass: target old rows are gone; new marker exists; log order includes DDL receipt, `[REAL DDL]`, `notifyTableIdChanged`,
old-region removal, and new puller initialization.

### Case 9: DDL barrier ordering

```sql
ALTER TABLE cc_tidb_cdc_test.cc_cdc_dml_main
    ADD COLUMN ddl_case_col VARCHAR(32) NULL;
INSERT INTO cc_tidb_cdc_test.cc_cdc_dml_main
    (username, email, ddl_case_col)
VALUES ('<marker>', '<marker>@test', 'insert_ok');
UPDATE cc_tidb_cdc_test.cc_cdc_dml_main
SET ddl_case_col = 'update_ok'
WHERE username = '<marker>';
```

Pass: target applies DDL before DML using the new column, final value is `update_ok`, and no
`CheckpointTs is greater than next ddl commitTs` appears.

### Case 10: partition init, add, and truncate

```sql
ALTER TABLE cc_tidb_cdc_test.cc_cdc_partition_main
    ADD PARTITION (PARTITION p4 VALUES LESS THAN (5000));
INSERT INTO cc_tidb_cdc_test.cc_cdc_partition_main
    (id, username, email)
VALUES (4101, '<marker>_p4', '<marker>_p4@test');
ALTER TABLE cc_tidb_cdc_test.cc_cdc_partition_main TRUNCATE PARTITION p0;
INSERT INTO cc_tidb_cdc_test.cc_cdc_partition_main
    (id, username, email)
VALUES (101, '<marker>_p0', '<marker>_p0@test');
```

Pass: the new partition is subscribed, p0 tableId replacement is handled, and both p4/p0 markers match.

### Case 11: mixed-case table

Run INSERT, UPDATE, DELETE, and `ALTER TABLE cc_CDC_MixedCase ADD COLUMN Case_Extra_Col_2 VARCHAR(32) NULL` using exact
case.

Pass: information-schema lookup, filter, DML, and DDL all preserve case and markers match. An intentionally wrong-case
configuration must remain clearly unsubscribed, not half-synced.

### Case 12: DDL job table

```sql
ALTER TABLE cc_tidb_cdc_test.cc_cdc_dml_main
    ADD INDEX idx_ddl_case_email (email);
ALTER TABLE cc_tidb_cdc_test.cc_cdc_dml_main
    DROP INDEX idx_ddl_case_email;
```

Pass: log order includes `Receive DDL`, `[DDL JOB]`, `[REAL DDL]`, `[REMOVE DDL JOB]`; DDL resolvedTs continues
advancing.

## Cases 13-18: recovery, load, restart, GC, and observability

### Case 13: `region_not_found`

Run only in a disposable multi-TiKV cluster. Split a small subscribed range, enable or accelerate that cluster's
ordinary region merge, continuously write markers, and wait for an old region id to be merged away. Record every PD
setting and restore it. Allow at most three merge windows of ten minutes each; use a new marker and region id per
window.

Do not use `unsafe-recover` and never delete a production region.

Pass: an actual `region_not_found` is followed by range reschedule and new initialization; markers match. Ordinary
split/merge may not deterministically hit the subscribed request, so use NOT TRIGGERED when appropriate.

### Case 14: sorter flush under bulk load

Save `asyncFlushFileIntervalSec` (default 20) and set it to 2 on the disposable task. Insert at least 20,000 markers in
batches, update 5,000, and delete 2,000.

Pass: both sides end with 18,000 markers; all 5,000 updated values match; deleted ids are absent; logs show
`[TIDB] real flush to file` or equivalent queue activity; no RocksDB/store-offer failure occurs. Restore the original
flush interval.

### Case 15: checkpoint restart

1. Write `<marker>_before` while running and wait for target.
2. Stop the task cleanly.
3. Write `<marker>_stopped` while stopped.
4. Restart from its saved checkpoint and write `<marker>_after`.

Pass: all three markers arrive; restart logs show subscribe/init. At-least-once replay is acceptable, loss is not.

### Case 16: parallel task and partition owner

Create or reconfigure a test task with `allParallel > 1` and enough worker slots. Use large ordinary tables plus the
partition table; execute truncate and partition DDL.

Pass: owner partitions process tableId changes, non-owners may log `Skip tryToAddPartitionTable: not owner`, and
aggregate target data is complete and not duplicated. Multi-TiKV alone does not cover this case.

### Case 17: GC safe point

Save settings, set `gcTtlSec=600`, `gcLagSec=60`, and `cdcGcUpdateIntervalSec=5`, and write markers continuously for at
least ten minutes.

Pass: `Begin Updated GC SafePoint` and `Updated GC SafePoint` recur, no sustained update failure appears, and data keeps
syncing. Restore settings.

### Case 18: log and metric cooldown

Idle for two minutes, then trigger split, leader switch, and deadline in separate marked windows.

Pass: in the two-minute idle window, `Fetch data rows:0` appears no more than four times per table, metrics appear 3-5
times, and `This table not initialized` appears no more than once per table. Abnormal states must still be diagnosable,
and final region metrics must return to zero. If the configured cooldown differs, record it and derive an equally
explicit count before execution.

## Combined stress

Run only after cases 1-18 have independent results. Require three TiKV, destructive opt-in, and saved cleanup commands.

In one window, combine:

1. lowered `cdcStubTimeout` with non-fatal deadline handling;
2. leader eviction;
3. region split;
4. `TRUNCATE TABLE cc_cdc_region_03` and post-truncate inserts;
5. ADD PARTITION p5 (`VALUES LESS THAN (6000)`) and insert ids in 5000-5999; case 10 already created p4;
6. continuous ordinary DML.

Pass only when split, truncate, partition, and continuous markers match; deadline, `not_leader`, and `epoch_not_match`
each appear with recovery; fatal patterns remain absent; final metrics are zero; a post-probe succeeds.

## Cleanup and report

In a finally-style cleanup:

- remove any evict-leader scheduler;
- restore deadline, fast-fail, flush, GC, and parallel settings;
- stop the disposable task;
- retain logs and case evidence until review completes;
- delete only the dedicated source/target databases and exact playground tag after confirmation.

Report template:

```markdown
## TiDB CDC integration result

- Code revision / dirty worktree:
- CloudCanal / TiDB versions:
- Topology and connectivity:
- Layer A tests/failures/errors/skipped:
- Layer B tests/failures/errors/skipped:
- Datasource smoke:
- Row V1/V2 physical-type lifecycle:
- Task id and log paths:
- Cases 1-18: status + marker + source/target counts + log evidence
- Combined stress:
- Final metrics and post-probe:
- Restored settings and remaining cleanup:
- First original error:
- Untested boundaries:
- Production-code changes made by the test:
```
