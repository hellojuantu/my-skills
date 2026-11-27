# Log Verification Reference

## Required Logs

- Main task log: `<task>_INCREMENT.log`
- Apply log: `apply_commit.log`
- Optional check log: `<check>_CHECK/diff.log`

For remote logs, collect the same paths over SSH. If the log server requires a password and there is no key, either allow interactive SSH or use `sshpass` through `CC_LOG_PASS`.

## Good Patterns

Deadline retry:

```text
Region grpc error:...DEADLINE_EXCEEDED
Begin to re schedule region request,reason:grpc_error
Re schedule region request success
Region is initialized
```

Leader retry:

```text
Region event error:not_leader
Begin to re schedule region request,reason:not_leader
Region is initialized
```

Epoch/range reload:

```text
Region event error:epoch_not_match
Begin to re schedule range request
Region is initialized
```

DDL:

```text
[DDL JOB]
[REAL DDL]
[REMOVE DDL JOB]
Complete DDL execution
Fetch data rows
```

Healthy final metrics:

```text
[METRICS] allRegionSize:<n>,uninitializedRegionSize:0,errRegionSize:0,liveRegionSize:<n>
```

Temporary nonzero region metrics during split, deadline, leader eviction, or DDL reload are acceptable if final metrics recover and a post-recovery DML probe syncs.

## Bad Patterns

Treat these as failure unless there is a known intentional shutdown:

```text
Process event failed
ErrPrewriteNotMatch
CheckpointTs is greater than next ddl commitTs
clusterIdMismatch
duplicateRequest
matched fastFailKeywords
Try to exist with System.exit
Offer event into store failed
Fetch ddl job table meta from pd is empty
Decode fails,value length is zero
```

## Data Verification

Prefer marker count checks over whole-table counts when tables have pre-task seed data.

Whole-table count differences are not enough to prove CDC loss. Compare row creation time against task creation/start time and check `apply_commit.log`. Rows created before incremental start are expected to be absent from a pure incremental task.

## Receive Log Notes

`SKIP_SPAN_...` can be normal when TiKV streams include events outside the subscription span. It is a failure only when the target table's own marker rows are missing or the skip marker corresponds to the subscribed table's raw row key/tableId.
