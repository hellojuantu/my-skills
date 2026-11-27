# CloudCanal TiDB CDC 18-Case Plan

Use a dedicated database such as `cc_tidb_cdc_test`. Keep marker values unique per run, for example `codex_<case>_<yyyyMMddHHmmss>`.

## Case 1: Multi-Table Same-Region Span Regression

Goal: verify raw span handling and comparable request conversion do not lose a table's own events when a TiKV region contains multiple table spans.

Method: subscribe multiple tables in adjacent schemas/tables or use `cc_cdc_region_01/02/03`. Insert 100 rows per table with table-specific marker values.

Verify: target marker counts equal source; main log has `Fetch data rows` for the subscribed table. `SKIP_SPAN_` for other tables is acceptable.

## Case 2: epoch_not_match / Region Split

Goal: verify old region epoch invalidation triggers range reload and new region subscription.

Method:

```sql
SPLIT TABLE `cc_tidb_cdc_test`.`cc_cdc_region_01` BETWEEN (0) AND (1000000) REGIONS 16;
```

Write rows before and after split.

Verify: log has `Region event error:epoch_not_match`, `Begin to re schedule range request`, and later `Region is initialized`; source/target marker counts match.

## Case 3: not_leader / Leader Switch

Goal: verify NotLeader updates leader and retries without losing data.

Method:

```bash
tiup ctl:v8.5.4 pd -u http://<pd-host>:2379 store
tiup ctl:v8.5.4 pd -u http://<pd-host>:2379 scheduler add evict-leader-scheduler <store-id>
sleep 8
tiup ctl:v8.5.4 pd -u http://<pd-host>:2379 scheduler remove evict-leader-scheduler-<store-id>
```

Write DML during eviction.

Verify: log has `Region event error:not_leader`, `reason:not_leader`, and later `Region is initialized`; final marker counts match.

## Case 4: DEADLINE_EXCEEDED / gRPC Stream Timeout

Goal: verify stream timeout releases old region state and resubscribes.

Manual prerequisite: set `cdcStubTimeout` low enough to trigger deadline. To test automatic retry instead of process fast-fail, clear or adjust `fastFailKeywords` so `DEADLINE_EXCEEDED` is not fatal, then restart the task.

Verify: log has `DEADLINE_EXCEEDED`, `reason:grpc_error`, `Re schedule region request success`, `Region is initialized`; post-timeout DML syncs.

## Case 5: PREWRITE + COMMIT

Goal: verify matcher joins PREWRITE and COMMIT correctly.

Method:

```sql
SET tidb_enable_async_commit = 0;
SET tidb_enable_1pc = 0;
BEGIN OPTIMISTIC;
UPDATE `cc_tidb_cdc_test`.`cc_cdc_txn_conflict`
SET `count_value` = `count_value` + 1, `remark` = 'prewrite_commit'
WHERE `id` = <test_id>;
COMMIT;
```

Verify: no `ErrPrewriteNotMatch`; target row has the committed value.

## Case 6: ROLLBACK / Transaction Conflict

Goal: verify rollback cleans unmatched prewrite and does not apply the rolled-back transaction.

Method: use two sessions on the same row with `tidb_enable_async_commit=0` and `tidb_enable_1pc=0`; commit session 2 first, then session 1 should fail or roll back.

Verify: apply log only contains the successful transaction; no later `ErrPrewriteNotMatch`.

## Case 7: COMMITTED Direct Path

Goal: verify default insert/update/delete committed events decode correctly.

Method: ordinary insert/update/delete on `cc_cdc_dml_main`.

Verify: target reflects final state; delete does not cause `Decode fails,value length is zero`.

## Case 8: TRUNCATE TABLE / tableId Change

Goal: verify tableId reload, old region cleanup, and new table subscription.

Method:

```sql
TRUNCATE TABLE `cc_tidb_cdc_test`.`cc_cdc_region_03`;
INSERT INTO `cc_tidb_cdc_test`.`cc_cdc_region_03` (...) VALUES (...);
```

Verify: log has `Receive DDL`, `[REAL DDL]`, `notifyTableIdChanged`, old region removal, new `Puller is initialized`; new marker rows sync.

## Case 9: DDL Barrier Ordering

Goal: verify DML does not pass unresolved DDL.

Method:

```sql
ALTER TABLE `cc_tidb_cdc_test`.`cc_cdc_dml_main` ADD COLUMN `ddl_case_col` VARCHAR(32) NULL;
INSERT INTO `cc_tidb_cdc_test`.`cc_cdc_dml_main` (...) VALUES (...);
UPDATE `cc_tidb_cdc_test`.`cc_cdc_dml_main` SET `ddl_case_col` = 'ok' WHERE ...;
```

Verify: target executes DDL before DML using the new column; no `CheckpointTs is greater than next ddl commitTs`.

## Case 10: Partition Init, ADD PARTITION, TRUNCATE PARTITION

Goal: verify partition tableId subscription, dynamic partition add, and partition tableId change.

Method:

```sql
ALTER TABLE `cc_tidb_cdc_test`.`cc_cdc_partition_main`
ADD PARTITION (PARTITION p4 VALUES LESS THAN (5000));

ALTER TABLE `cc_tidb_cdc_test`.`cc_cdc_partition_main` TRUNCATE PARTITION p0;
```

Insert rows into affected partitions.

Verify: log has add-partition subscription and tableId change for truncated partition; marker rows in each partition sync.

## Case 11: Mixed-Case Schema/Table Names

Goal: verify `information_schema` tableId lookup and table filters preserve case semantics.

Method: use `cc_CDC_MixedCase` or create a mixed-case schema/table and run insert/update/delete plus ADD COLUMN.

Verify: initialization and DDL filtering find the table; marker rows sync. If config case differs intentionally, it should be clearly unsubscribed, not half-synced.

## Case 12: DDL Subscription Table

Goal: verify the DDL puller subscribes TiDB's DDL job table.

Method:

```sql
ALTER TABLE `cc_tidb_cdc_test`.`cc_cdc_dml_main` ADD INDEX `idx_ddl_case_email` (`email`);
ALTER TABLE `cc_tidb_cdc_test`.`cc_cdc_dml_main` DROP INDEX `idx_ddl_case_email`;
```

Verify: log has `Receive DDL`, `[DDL JOB]`, `[REAL DDL]`, `[REMOVE DDL JOB]`; DDL resolvedTs advances.

## Case 13: region_not_found / Region Disappears

Goal: cover the region-not-found branch.

Method: split first, then allow/force merge if the environment supports region merge. Keep writing DML.

Verify: log has `region_not_found`, `Begin to re schedule range request`, new region initialization, and matching marker counts.

## Case 14: Sorter Flush / Bulk Writes

Goal: verify memory cache, file flush, and fetchByTable under load.

Method: lower flush thresholds if possible and write tens of thousands of rows with mixed update/delete.

Verify: log has `[TIDB] real flush to file` or flush queue activity, no RocksDB exception, no `Offer event into store failed`, and final counts match.

## Case 15: Task Restart / Checkpoint Recovery

Goal: verify restart continues from checkpoint without data loss.

Method: write before stop, during stop, and after restart.

Verify: restart logs show subscribe/init; post-restart marker rows sync; pre-task seed rows are not treated as incremental loss.

## Case 16: Parallel Task / Region Split and Partition Owner

Goal: verify `allParallel > 1` table slicing and partition ownership.

Method: run parallel task with large ordinary tables and partition tables; execute truncate and partition DDL.

Verify: split owner logs are expected; non-owner partition logs may say `Skip tryToAddPartitionTable: not owner`; aggregate target data is complete and non-duplicated.

## Case 17: GC SafePoint

Goal: verify GC safe point update does not interrupt CDC.

Method: set `gcTtlSec > 0`, `gcLagSec > 0`, lower `cdcGcUpdateIntervalSec`, and run for at least 10 minutes while writing.

Verify: log has `Begin Updated GC SafePoint` and `Updated GC SafePoint`; no sustained `Update GC SafePoint failed`; data sync continues.

## Case 18: Log and Metric Cooldown

Goal: verify normal logs are readable while abnormal states remain diagnosable.

Method: idle for two minutes, then run split/not_leader/deadline.

Verify: DDL tick is summarized, `Fetch data rows:0` is cooled down, metrics every 30s remain useful, and `This table not initialized` is not spammed.

## Combined Stress Case

Run `DEADLINE_EXCEEDED`, `not_leader`, `epoch_not_match`, `TRUNCATE TABLE`, `ADD PARTITION`, and DML in one window.

Pass criteria:

- Split table rows before and after split match source/target.
- Truncate table post-DDL rows match source/target.
- Add partition rows match source/target.
- Log contains expected errors and recovery, and does not contain fatal markers.
- Final metrics return to `uninitializedRegionSize:0,errRegionSize:0`.

Example observed pass: `DEADLINE_EXCEEDED` 58, `not_leader` 24, `epoch_not_match` 15, range reload 32, with no `Process event failed`, no `matched fastFailKeywords`, no `System.exit`, no `Duplicate`, no `Schedule skip`, and marker counts all equal.
