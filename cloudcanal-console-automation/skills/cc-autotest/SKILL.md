---
name: cc-autotest
description: Run CloudCanal N×N link batches, including temporary data, faker changes, consistency checks, and reports. Use for batch link verification, not for a single manual job.
---

# CloudCanal Autotest

Use this reference when the user asks for N*N datasource link testing, ordinary development branch testing, temporary datasets, faker data, consistency checks, or test reports.

## Test Plan Shape

The current run is the dev gate. It creates one multi-table CloudCanal job per datasource pair/profile or explicit user table set, initializes temporary source data when using the default profile, prepares the target namespace when using the default profile, creates a full+increment+structure task, starts it, waits for full completion, runs a local count check, runs a CloudCanal check child, waits for incremental readiness, runs an incremental-baseline local count check and check-child replay, generates faker CRUD when using the default profile, runs another local count check, replays the CloudCanal check child again, collects lightweight task-log evidence, and reports.

One CloudCanal job may contain multiple tables. The core profile must create one task containing the profile tables; do not split into one task per table unless the frontend/source-target model requires separate jobs.

There are two integration-test entry points:

- `autotest-batch-run`: N*N matrix execution over datasource pairs, normally using adapter default temporary datasets.
- `autotest-run`: one source-to-target link execution. It can use the adapter default temporary dataset or explicit user tables through the same `--table`, `--table-map`, `--column-map`, `--source-schema-json`, `--target-schema-json`, and `--mapping-json` arguments used by `create-job`.

Default profiles are only default temporary test datasets. User-provided tables are ordinary CloudCanal job objects and should still run the full test phases when requested. The runner must not invent table semantics for user tables: if explicit tables are passed, the task payload and local count/check use those tables, while destructive initialization and generic faker CRUD are skipped unless the user separately prepares data or a datasource-specific mutator is implemented.

## Commands

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-deps
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-install-deps --adapter mysql-family
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-selftest
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-plan --test-mode dev --batch-size 5
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-matrix \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --batch-size 5 --summary-only
```

Run one generated batch end to end:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-batch-run \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --cluster-id "$CC_CLUSTER_ID" \
  --source-type MySQL --target-type MySQL \
  --batch-size 5 --batch-no 1 \
  --credential-json @/tmp/cloudcanal-autotest-credentials.json \
  --rows 1000 --crud-rounds 1000 \
  --wait-after-crud-seconds 30 --wait-check-child-seconds 180
```

Batch size is adjustable. The default is 5 pairs per batch for safer worker/resource usage. Use `--batch-size 0` to put all selected pairs into one batch, and raise `--max-concurrency` when the CloudCanal cluster and source/target databases have enough capacity:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-batch-run \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --cluster-id "$CC_CLUSTER_ID" \
  --batch-size 0 --max-concurrency 6 \
  --credential-json @/tmp/cloudcanal-autotest-credentials.json \
  --output-dir /tmp/cloudcanal-autotest-dev-001
```

Temporarily exclude a datasource family when its environment is noisy or under investigation:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-batch-run \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --cluster-id "$CC_CLUSTER_ID" \
  --matrix-json @/tmp/cloudcanal-autotest-matrix.json \
  --exclude-type TiDB
```

The batch runner writes `batch-result.json`, `batch-report.md`, and one `pair-N-run.json` file per pair. It does not delete jobs or temporary datasets unless `--cleanup-after-run` is explicitly passed.

Default batch data volume is intentionally around 1k seed rows per profile table and 1k random CRUD rounds. Use smaller explicit values only for local smoke testing.

The default verification flow is staged:

1. Wait for structure/full completion.
2. Run a local `count` comparison. This is a quick sanity check, not a replacement for CloudCanal's checker.
3. Create and wait for a CloudCanal check child job. This is the detailed loss/diff check. The autotest runner must follow the frontend lifecycle: `INIT` with `fsmActive=false` uses `activefsm`, `STOP` uses `start`, and `WAIT_START` or `INIT` with `fsmActive=true` means CloudCanal has already submitted/activated the work and the runner should wait for the scheduler/worker instead of issuing another start or active-fsm call. Do not ask the user to manually start check children from the page.
4. Wait for frontend-equivalent incremental readiness (`CATCH_UP` or `INCRE` with the incremental task running).
5. Run an incremental-baseline local `count` comparison before generating new changes.
6. Replay the same CloudCanal check child job and wait for baseline loss/diff results.
7. Generate random CUD on the source. Adapters may skip provable local duplicate-key collisions; the run only requires enough successful data changes.
8. Run another local `count` comparison.
9. Replay the same CloudCanal check child job and wait for post-CUD loss/diff results. Replay is an async console job that resets and activates FSM when appropriate, so wait/query first. Use `continue-job`/`active-fsm` only when the frontend-equivalent FSM state requires it; do not treat `WAIT_START` as a reason to force another activation.
10. Save lightweight stage log snapshots for full, incremental/apply-related log files, and check logs.

Stage log snapshots are evidence, not a second product-specific rule engine. The runner defaults to necessary generic lines such as ERROR-level lines, exception/root-cause continuation lines, connection-loss text, and nonzero `loss`/`diff`, plus a short tail and the original log path/end row. WARN lines are too noisy for default reports; pass `--include-warn-logs` only when a case needs deeper WARN-level diagnosis. Do not add datasource-specific case rules to the shared runner; put datasource-specific interpretation in adapter docs or a separate focused skill.

The local SQL checker is a quick sanity check. Default RDB autotest profiles must not include no-PK tables because CloudCanal's default no-PK behavior is not stable enough for routine N*N regression. There is no legacy no-PK profile in this skill; use a separate focused case and explicit user tables if no-PK compatibility needs investigation.

Batch failures are isolated, not cleaned. By default the runner collects diagnostics for a failed pair and stops the failed data job before moving to the next pair. This keeps the console job and temporary schemas/topics/indexes available for review while preventing a failed full or incremental task from polluting the next test. Pass `--no-stop-failed-job` only when you intentionally want the failed task to keep running for live debugging.

If a batch fails after a datasource endpoint was corrected, remember that already-created jobs still contain the old copied datasource config. For clean N*N validation, prefer rerunning the affected pair or batch after deleting the old job and explicitly cleaning the old temporary schemas/topics/indexes. If you choose to resume the old job, first repair the job `DATASOURCE` configs and retry the failed console task as documented in `../cc-job-operations/SKILL.md`; also make sure the temporary source dataset exists on the endpoint now copied into the job.

When full migration is complete but the incremental task remains `INIT`/`STOP` with `fsmActive=false`, call the frontend-equivalent `activefsm` flow and then wait for incremental readiness. Do not treat `FULL COMPLETE` plus `conditionHealthStatus=UNHEALTHY` as a product failure by itself; use `haveException`, explicit task failure, task error messages, local count/check results, and ERROR log evidence.

Autotest defaults should be production-useful without remembering many flags: one-shot full CloudCanal check, incremental-baseline local/check-child validation, 1k seed rows, 1k CRUD rounds, local count checks, check child replay, stage ERROR log snapshots, post-full FSM activation, and check-child start/activation are all default behaviors. Extra flags should narrow or override behavior, not be required to make the standard test correct.

When one pair fails for an autotest-local reason such as a transient adapter exception, do not mark the whole matrix as a product failure. Record the pair status, collect job ids and console failure summaries, then continue or resume from the next pair. Random faker duplicate-key collisions are normal when the adapter can prove they are local collisions; count and skip them. Treat a CloudCanal task failure, async console failure, consistency mismatch, or missing expected data as a link failure until logs prove otherwise.

Report pair phases separately. A pair can be `CREATE_OK` but still fail later at `START_FAIL`, `FAKER_ERROR`, `VERIFY_FAIL`, or `CHECK_CHILD_FAIL`. Do not explain a failed batch as "task creation failed" unless the create phase itself failed.

Use the staged runner semantics when analyzing results:

- `FULL_FAIL`: CloudCanal did not finish full migration; inspect task health, unfinished table progress, and task logs before checking target data.
- `FULL_VERIFY_FAIL`: full migration completed but source/target SQL snapshots differ; add or inspect the CloudCanal check child before treating it as only a local checker issue.
- `INCREMENT_READY_FAIL`: full completed but the job did not enter frontend-equivalent incremental readiness (`CATCH_UP` or `INCRE` with `INCREMENT` running).
- `INCREMENT_BASELINE_VERIFY_FAIL`: the job entered incremental mode, but source/target snapshots already differ before new faker CUD. Stop before generating more changes and inspect the baseline check child/log evidence.
- `FAKER_FAIL`: local data generator failed to produce useful changes. Duplicate key attempts during random CRUD can be local faker collisions and should be counted/skipped by adapters when provable.
- `INCREMENT_VERIFY_FAIL`: incremental CUD ran but source/target SQL snapshots differ; still create/check the CloudCanal check child when possible.
- `CHECK_CHILD_FAIL`: CloudCanal check child was created but did not complete cleanly or reported loss/diff.

Do not make case-by-case conclusions from datasource type alone. First collect the generic evidence chain: job state, task health, unfinished tables/objects, necessary task-log grep samples, optional direct source/target sanity reads through adapters, and CloudCanal check child result. For connection errors such as `EOFException`, `Connection reset`, or "unexpectedly lost", verify whether the source temporary objects can be read directly before calling the source system bad; this distinguishes a source-data problem from a CloudCanal worker/reader/runtime failure.

Use description filters when the user scopes the run, for example `--desc-prefix codex-`. Do not include all visible datasources just because they are reachable.

Keep default batch execution conservative. Same-source concurrent pairs can pollute incremental logs with each other's temporary DDL/DML, especially for binlog-style sources. Use `--max-concurrency > 1` only when the selected pairs are isolated enough or the user explicitly wants to trade determinism for speed.

`autotest-matrix --ready-only` and the default batch runner should select only `READY` pairs: both adapters can initialize source data, prepare target objects, generate source changes, and run a local count/digest snapshot. Use `--include-unready` only for routed-but-not-local-verified pairs where the user has already prepared source data and accepts CloudCanal-check-only validation.

`autotest-run` also checks adapter readiness before a live staged run. A routed-only datasource may still be useful for dry-run payload review or a deliberately narrowed CloudCanal-only workflow, but the default live flow will fail early with `ADAPTER_NOT_READY` instead of pretending a temporary dataset exists.

Single pair dev smoke:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-run \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --cluster-id "$CC_CLUSTER_ID" \
  --source-ds-id 10 --target-ds-id 2 \
  --source-schema cc_auto_src --target-schema cc_auto_dst \
  --source-password "$SRC_PASSWORD" --target-password "$DST_PASSWORD"
```

`autotest-run` starts or continues the created job, waits for any full phase, runs local count and CloudCanal CHECK child checks, and repeats those checks at the incremental baseline. With new temporary fixtures it then runs 1,000 faker CRUD rounds by default before the final count and CHECK replay. When `--table` or `--table-map` supplies existing tables, it skips faker changes and still runs the enabled consistency checks. Verify incremental delivery for those tables with a marked change after capture is ready and a native target readback. Stage logs are saved under `/tmp/cloudcanal-autotest-single-*`. Use `--no-start-after-create`, `--no-sql-check`, `--no-add-check-child`, `--crud-rounds 0`, or `--no-collect-stage-logs` only when intentionally narrowing the run.

Before start/continue, the runner queries the saved job first. If the job is in the frontend post-structure state, it continues with `active-fsm`; otherwise it uses the normal start API or records that the job is already active.

For a dry-run payload check:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-run \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --cluster-id "$CC_CLUSTER_ID" \
  --source-ds-id 10 --target-ds-id 2 \
  --source-schema cc_auto_src --target-schema cc_auto_dst \
  --source-password "$SRC_PASSWORD" --target-password "$DST_PASSWORD" \
  --dry-run
```

Credential file shape:

```json
{
  "datasources": {
    "10": {"user": "root", "password": "******"},
    "11": {"user": "root", "password": ""},
    "2": {"user": "root", "password": "******"}
  },
  "defaults": {
    "MySQL": {"user": "root", "password": "******"}
  }
}
```

The empty string password in the example is intentional. Credential resolution must distinguish empty string from unset.

## Adapter Architecture

Database behavior lives under `scripts/cc_console/db_adapters/`; `autotest.py` only orchestrates.

- `base.py`: shared adapter contract, dependency detection, temp schema guard.
- `object_common.py`: namespace-safe object naming plus shared object-style seed/change/snapshot flow for topics, queues, keys, indexes, collections, and files.
- `mysql_family.py`: implemented MySQL protocol profile and data operations for MySQL/TiDB/MariaDB/AuroraMySQL/GaussDBForMySQL/PolarDbMySQL/OceanBase/TDSQL/DRDS/PolarDbX, with StarRocks/Doris/SelectDB target preparation/check support where MySQL protocol works.
- `rdb.py`: implemented core RDB temporary dataset operations for PostgreSQL/PolarDBPg/AuroraPostgreSQL/Greenplum/Cloudberry/Redshift/GaussDBForOpenGauss/GaussDB/KingbaseES/Vastbase/Hologres, Oracle, SQLServer, Db2, Hana, Dameng, ClickHouse, GreptimeDB, and TDengine.
- `mq.py`: Kafka/AutoMQ/AmazonMSK support local count and digest checks. RabbitMQ supports count checks. Pulsar and RocketMQ can produce test messages, but their local adapters do not verify complete topic snapshots or clean up topics. Use CloudCanal CHECK for an existing dataset or verify through the engine's management interface.
- `cache.py`: Redis/ElastiCache, Lindorm.
- `search.py`: ElasticSearch.
- `document.py`: MongoDB/DocumentDB, DynamoDB.
- `lakehouse.py`: fsspec-backed file objects for OssFile/S3File/SshFile, plus routed-but-not-local-verified GoogleDrive/Yuque, Hive/Hudi/Iceberg/Paimon/DeltaLake/Kudu/MaxCompute/DataLakeFormation, and Tunnel. Snowflake and Spanner have native table adapters.
- `api_ai.py`: RagApi and LLM-style endpoints are routed-only for datasource/job workflows. They do not have a built-in generic CRUD protocol or profile tables; add a dedicated adapter from a frontend/backend trace before marking any API/AI family as local-data `READY`.

All datasource types in `clouddm-web/src/views/dataSourceGroup.json` must route to an adapter. If the frontend adds a type, update datasource aliases and the adapter registry before claiming full coverage.

## Current Coverage Rules

- Adapter routing covers the frontend datasource type list.
- A routed adapter is not the same as local data verification readiness. `ROUTED` means datasource/job payloads can be reasoned about and the type is not lost; `READY` means the adapter can initialize temporary data, mutate it, clean it, and compare source/target snapshots.
- Do not mark a datasource family as automated until it can initialize a temporary dataset, generate changes, and verify target consistency or has a documented alternative verification method.
- Cross-family SQL consistency uses source and target snapshots from their own adapters. Do not reuse a MySQL target checker for PostgreSQL/Oracle/SQLServer targets.
- MQ/cache/search/document/file/lakehouse links need family-specific data models: messages, keys, documents, indexes, files, partitions, or API payloads. Do not fake a catalog/table system with local files unless that is the actual frontend/source contract for the datasource.
- RDB create payloads must include selected source columns in `sourceSchema`. The runner reports `sourceColumnCounts` and fails early when an RDB table would be created with empty columns, because full sync can otherwise write target default values while incremental data appears normal.

Current non-RDB local-data `READY` families are Kafka/AutoMQ/AmazonMSK, RabbitMQ, Redis/ElastiCache, Lindorm, ElasticSearch, MongoDB/DocumentDB, DynamoDB, and explicit fsspec-backed OssFile/S3File/SshFile. Use `autotest-deps` to check the capabilities of a specific adapter before choosing a pair or verification mode.

## MySQL Core Profile

`mysql-core-4` is the default automated profile and contains four primary-key tables in one task:

- `pk_int_table`
- `pk_int_auto_table`
- `pk_varchar_table`
- `pk_timestamp_table`

It covers the first stable automated subset of the detailed MySQL Excel plan: int PK, auto-increment PK, varchar PK, timestamp PK, multi-table structure/full/increment sync, and one-shot check child job wiring. The skill intentionally has no default no-PK profile.

Other implemented RDB default profiles follow the same shape and table names, with database-specific DDL and connection behavior in `rdb.py`: `postgres-core-4`, `oracle-core-4`, `sqlserver-core-4`, `db2-core-4`, `hana-core-4`, `dameng-core-4`, and `clickhouse-core-4`.

Initialization data must be deterministic and unique. If init hits a duplicate key, fix the adapter/profile because the test dataset is incomplete. During random CRUD, duplicate insert attempts may be skipped and counted when the adapter can prove they are local faker collisions rather than task-side errors.

## Reporting

Store run JSON outside the skill directory, then render markdown:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-report \
  --run-json /tmp/cloudcanal-autotest-run.json \
  --output /tmp/cloudcanal-autotest-report.md
```

Reports must include environment URL, cluster id, datasource ids, schema names, job ids, adapter family, profile, pass/fail, phase summary, local count/digest mismatches, CloudCanal check child loss/diff, stage log evidence paths/categories/samples, and cleanup status.

Clean temporary datasets only after the user explicitly asks:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" autotest-cleanup-dataset \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10 --schema cc_auto_src --password "$SRC_PASSWORD"
```

For adapters that manage individual objects, repeat `--table` for the exact temporary object names listed in the run report. If a create request returns no task ID, locate the job and confirm its state before cleaning up the datasets.

The runner derives automatic target names from the temporary target namespace for adapters that manage individual objects. To verify a previous run directly, pass the recorded `--table-map SOURCE=TARGET` pairs.

For N*N batch execution, after each batch report created job ids, schemas/topics/indexes/keys, check result, and the next batch number. Do not delete jobs or temporary data automatically. Ask or wait for the user to say cleanup/delete before calling `delete-job`, datasource `delete`, or adapter cleanup commands.

When the user does ask for cleanup, delete child check jobs before parent jobs and use the FSM-aware delete path:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" delete-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id "$JOB_ID" --delete-children --stop-first --inactivate-fsm
```

This avoids the Reakh-observed failure where a check child in an active FSM state blocks both its own deletion and parent job deletion.
