---
name: cc-datajob
description: Create CloudCanal data jobs and change subscriptions through the Console API. Use for job creation and subscription edits, not for start, stop, position changes, or N×N batch tests.
---

# Data Job Automation

Use the bundled `$CLOUDCANAL_SKILL/scripts/create_datajob.py create-job` command for task creation. The command builds `sourceSchema`, `targetSchema`, and `mappingDef` from console dynamic APIs plus frontend-aligned datasource-group rules.

## Create

Normal database to database:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" create-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --cluster-id 1 \
  --source-ds-id 10 --target-ds-id 11 \
  --source-db auto_test --target-db auto_test \
  --table src_table=dst_table \
  --mode full-sync --job-name auto_test_sync \
  --non-interactive --dry-run
```

MQ source to database target:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" create-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --cluster-id 1 \
  --source-ds-id 20 --target-ds-id 10 \
  --source-type kafka --target-type mysql \
  --target-db auto_test \
  --table demo_topic=demo_table \
  --mode increment --non-interactive --dry-run
```

Use `--source-schema-json`, `--target-schema-json`, `--mapping-json`, `--processor-config-json`, and `--extra-json` when a complex frontend trace is available or the datasource pair is not yet verified by the script.

For RDB sources, the builder queries selected columns and writes them into `sourceSchema`, matching the frontend create flow. Do not create a full/full-sync RDB job with empty table `columns`; the command fails early because that payload can make full sync write target default values even though incremental sync later looks healthy.

The create API returning `dataJobId` does not mean the backend async creation flow is complete. For complex sources, creation continues in a console job such as `DATA_JOB_CREATE`; wait for the saved job/console job to finish before starting, running faker data, or adding check children. If the async flow fails, query the console job summary first and record `consoleJobId`, failed step, handler, and message.

Datasource fields are copied into the job at create time. The job keeps its own `DATASOURCE` config entries such as `host`, `userName`, `password`, `useSSL`, `proxyMode`, and family-specific values. Changing the datasource object afterward only affects new jobs. For existing jobs, use the job config repair flow in `../cc-job-operations/SKILL.md`.

When building new jobs, query and merge datasource-specific config from the console instead of hardcoding it. Current create-job/autotest behavior must preserve at least:

- TiDB source: `pdHost` plus the selected `host`; a stale PD or SQL host causes async create to fail during TiDB CDC initialization.
- StarRocks/Doris/SelectDB source or target: HTTP/FE/BE address fields such as `privateHttpHost`, `publicHttpHost`, `feHttpAddr`, and `beThriftAddr` when returned by datasource config.
- Proxy settings: only copy proxy fields when proxy mode is enabled; do not force proxy defaults into ordinary jobs.
- Passwords and other secrets are not reliably queryable from saved datasource detail. Pass them through user input, a credential JSON file, or a frontend-captured payload when a repair or new job needs them.

For exact frontend replay, save the browser-captured `DataJobData` payload outside the skill directory and call the frontend service directly:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" precheck \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --stage final --payload-json @DataJobData.json

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" call-service \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --service ccDataJobCreate --payload-json @DataJobData.json --dry-run
```

Do this for teammate-facing automation until the named `create-job` builder has been dry-run compared against that exact frontend payload. Delete captured payloads after verification if they contain passwords, ids, or table names that should not be shared.

## Modes

- `--mode full` or `migration`: migration-style full task with structure migration enabled by default.
- `--mode full-sync` or `sync`: sync task with initial full phase.
- `--mode increment`: incremental sync only.
- `--mode check`: check task.
- `--mode struct`: structure migration task.

## Mapping Rules

The command queries table and column mapping rules and chooses the server default unless overridden by `--table-rule` or `--column-rule`.

Frontend-aligned special branches currently include:

- MQ source to hasSchema target: `ANY_SCHEMA` + `TOPIC_TABLE`.
- MQ source to normal DB target: `ANY_DB` + `TOPIC_TABLE`.
- MQ to MQ: `TOPIC_TOPIC` for Kafka/AutoMQ/AmazonMSK, RocketMQ, and Pulsar target families.
- DB to MQ/RagApi: `TABLE_TOPIC`.
- DB to Redis/ElastiCache: `TABLE_KEYPREFIX`.
- DB or ES to ElasticSearch: `TABLE_INDEX` or `TABLE_TABLE`.
- hasSchema source and target: `DB_DB` + `SCHEMA_SCHEMA` + `TABLE_TABLE` + `COLUMN_COLUMN`.
- non-hasSchema source to hasSchema target: `DB_SCHEMA` + `TABLE_TABLE` + `COLUMN_COLUMN`.
- DynamoDB source/target no-db table mapping.

## Frontend Trace Required

Do not rely on the simplified builder alone for these cases. Capture the frontend request and replay or compare it:

- `processorConfigList`: virtual columns, implicit columns, field transforms, wide tables, LLM embedding/chat.
- Table-level data filters and target update conditions: `dataFilter`, `dstUpdateCondition`.
- Target partition/table options: DRDS, TDSQL MySQL, StarRocks/Doris/SelectDB/Iceberg/Paimon/DeltaLake partition expressions, Greptime time indexes, Hive partition keys/file format/compress.
- `schemaWhiteListLevel === DB`, table pattern selection, black action lists, custom specified PKs.
- MQ/Pulsar/RabbitMQ/Tunnel schema-less formats, tenants/namespaces/vhosts/exchanges, default DDL/data topics and partition counts.
- DynamoDB multi-target mapping and flattened source schema replay.
- Any task that depends on `advancedSetting`, `syncPartitionInfo`, `migrationPropertiesConfig`, `patternMeta`, loop/cycle fields, or datasource-specific WebOp options.

## Modify Subscription

Use `edit-job` for common add-table and reduce-table flows. It builds the same top-level payload used by the frontend `Process.vue` submit path:

- `sourceAddConfig`, `targetAddConfig`, `addMappingConfig` for newly added objects.
- `srcSchemaWithoutAdd`, `dstSchemaWithoutAdd`, `mappingConfigWithoutAdd` retain the current subscription after removing the selected objects and their mappings. Explicit JSON options override these fields.
- `reduceConfig` contains the removed source objects. Oracle and ObForOracle destinations also receive `targetReduceConfig` for removed targets.
- `processorConfsWithoutAdd` preserves the job’s saved processors. Pass `--processor-without-add-json '[]'` to clear them. `--add-processor-config-json` supplies processors for the addition.

Add a table:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" edit-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --cluster-id 1 --job-id 21 \
  --add-table src_table=dst_table \
  --source-db auto_test --target-db auto_test \
  --dry-run
```

Remove a subscribed source table:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" edit-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --cluster-id 1 --job-id 21 \
  --remove-table old_table \
  --source-db auto_test \
  --dry-run
```

For full-task edit mode, add `--full` to use `updatetransferobjectforfull`.

For advanced reduce/remap/processor cases, inspect the frontend `Process.vue` payload and either pass exact fragments with `--reduce-config-json`, `--source-schema-without-add-json`, `--target-schema-without-add-json`, `--mapping-without-add-json`, `--processor-without-add-json`, and `--add-processor-config-json`, or replay the full frontend payload:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-transfer-object \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 21 --payload-json @UpdateTransferObjFO.json --dry-run
```

For RDB add-table edits, `edit-job` queries source columns and fills `sourceAddConfig` columns. Do not submit an add-table payload with empty source columns.

## Dynamic Extras

Before creating an unfamiliar pair, run:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" job-extra-configs \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --source-type mysql --target-type starrocks --defaults
```

Pass returned defaults or user decisions with `--extra-json`.

## Frontend Precheck And Queries

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" precheck \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --stage final --payload-json @dataJobData.json

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-simple-jobs \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE"

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-check-tasks \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE"
```

Use `generate-migration-tip --payload-json @file` for the frontend `generateMigrationTip` payload, especially when partition, clean-target, or edit-mode fields are involved.

If an endpoint exists in the frontend but has no named command yet, use `call-service` for parity and record the API row from `audit_frontend_parity.py` before adding a wrapper. Use `call-api` only when you have a raw path instead of a frontend service key.
