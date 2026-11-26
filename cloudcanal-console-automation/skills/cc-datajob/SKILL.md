---
name: cc-datajob
description: Create CloudCanal data jobs and change subscriptions through the Console API.
---

# Data job automation

Use `$CLOUDCANAL_SKILL/scripts/create_datajob.py create-job` to create a task. The command builds `sourceSchema`, `targetSchema`, and `mappingDef` from console dynamic APIs and from the frontend datasource-group rules.

## Create

Database to database:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" create-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --cluster-id 1 \
  --source-ds-id 10 --target-ds-id 11 \
  --source-db dev_demo --target-db dev_demo \
  --table src_table=dst_table \
  --mode full-sync --job-name dev_demo_sync \
  --non-interactive --dry-run
```

MQ source to a database target:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" create-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --cluster-id 1 \
  --source-ds-id 20 --target-ds-id 10 \
  --source-type kafka --target-type mysql \
  --target-db dev_demo \
  --table demo_topic=demo_table \
  --mode increment --non-interactive --dry-run
```

Use `--source-schema-json`, `--target-schema-json`, `--mapping-json`, `--processor-config-json`, and `--extra-json` when you have a complex frontend trace, or when the script has not verified this datasource pair.

For an RDB source, the builder queries the selected columns and writes them into `sourceSchema`. That matches the frontend create flow. Do not create a full or full-sync RDB job with empty table `columns`. The command fails early. That payload can make full sync write target default values while incremental sync later looks healthy.

A `dataJobId` from the create API does not mean the backend async create has finished. For a complex source, creation continues in a console job such as `DATA_JOB_CREATE`. Wait for the saved job or console job to finish. Before the wait ends, do not start the job. Before the wait ends, do not add check children. If the async flow fails, query the console job summary first. Record `consoleJobId`, the failed step, the handler, and the message.

The create call copies datasource fields into the job. The job keeps its own `DATASOURCE` config. That includes `host`, `userName`, `password`, `useSSL`, `proxyMode`, and family-specific values. Editing the datasource object later affects only new jobs. For an existing job, use the repair flow in `../cc-job-operations/SKILL.md`.

When you build a new job, query datasource-specific config from the console. Merge that config into the job. Do not hardcode it. Keep these fields when the console returns them.

- TiDB source: `pdHost` plus the selected `host`. A stale PD or SQL host makes async create fail during TiDB CDC initialization.
- StarRocks, Doris, or SelectDB source or target: HTTP, FE, and BE address fields such as `privateHttpHost`, `publicHttpHost`, `feHttpAddr`, and `beThriftAddr`.
- Proxy settings: copy proxy fields only when proxy mode is enabled. Do not force proxy defaults into an ordinary job.
- Passwords and other secrets are not reliably readable from saved datasource detail. Pass them from user input, a credential JSON file, or a frontend-captured payload when a repair or a new job needs them.

For an exact frontend replay, save the captured `DataJobData` payload outside the skill directory. Call the frontend service directly.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" precheck \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --stage final --payload-json @DataJobData.json

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" call-service \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --service ccDataJobCreate --payload-json @DataJobData.json --dry-run
```

Do this for automation you will hand to someone else, until `create-job` has been dry-run compared with that exact frontend payload. Delete a captured payload after verification if it contains passwords, ids, or table names that should not be shared.

## Modes

- `--mode full` or `migration`: a migration-style full task. Structure migration is on by default.
- `--mode full-sync` or `sync`: a sync task with an initial full phase.
- `--mode increment`: incremental sync only.
- `--mode check`: a check task.
- `--mode struct`: a structure migration task.

## Mapping rules

The command queries table and column mapping rules. It chooses the server default unless you pass `--table-rule` or `--column-rule`.

Current frontend-aligned branches:

- MQ source to a hasSchema target: `ANY_SCHEMA` and `TOPIC_TABLE`.
- MQ source to a normal DB target: `ANY_DB` and `TOPIC_TABLE`.
- MQ to MQ: `TOPIC_TOPIC` for Kafka, AutoMQ, AmazonMSK, RocketMQ, and Pulsar target families.
- DB to MQ or RagApi: `TABLE_TOPIC`.
- DB to Redis or ElastiCache: `TABLE_KEYPREFIX`.
- DB or ES to ElasticSearch: `TABLE_INDEX` or `TABLE_TABLE`.
- hasSchema source and target: `DB_DB`, `SCHEMA_SCHEMA`, `TABLE_TABLE`, and `COLUMN_COLUMN`.
- non-hasSchema source to a hasSchema target: `DB_SCHEMA`, `TABLE_TABLE`, and `COLUMN_COLUMN`.
- DynamoDB source or target: no-db table mapping.

## Frontend trace required

Do not rely on the simplified builder alone for these cases. Capture the frontend request. Replay the request. Or compare the simplified builder against the request.

- `processorConfigList`: virtual columns, implicit columns, field transforms, wide tables, LLM embedding or chat.
- Table-level data filters and target update conditions: `dataFilter`, `dstUpdateCondition`.
- Target partition or table options: DRDS, TDSQL MySQL, StarRocks, Doris, SelectDB, Iceberg, Paimon, DeltaLake partition expressions, Greptime time indexes, Hive partition keys, file format, and compress.
- `schemaWhiteListLevel === DB`, table pattern selection, black action lists, and custom specified primary keys.
- MQ, Pulsar, RabbitMQ, and Tunnel schema-less formats, tenants, namespaces, vhosts, exchanges, default DDL or data topics, and partition counts.
- DynamoDB multi-target mapping and flattened source schema replay.
- Any task that depends on `advancedSetting`, `syncPartitionInfo`, `migrationPropertiesConfig`, `patternMeta`, loop or cycle fields, or a datasource-specific WebOp option.

## Modify subscription

Use `edit-job` for a common add-table or reduce-table flow. It builds the same top-level payload as the frontend `Process.vue` submit path.

- `sourceAddConfig`, `targetAddConfig`, and `addMappingConfig` are the newly added objects.
- `srcSchemaWithoutAdd`, `dstSchemaWithoutAdd`, and `mappingConfigWithoutAdd` keep the current subscription after the selected objects and their mappings are removed. Explicit JSON options override these fields.
- `reduceConfig` contains the removed source objects. Oracle and ObForOracle destinations also receive `targetReduceConfig` for removed targets.
- `processorConfsWithoutAdd` keeps the job's saved processors. Pass `--processor-without-add-json '[]'` to clear them. `--add-processor-config-json` supplies processors for the addition.

Add a table:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" edit-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --cluster-id 1 --job-id 21 \
  --add-table src_table=dst_table \
  --source-db dev_demo --target-db dev_demo \
  --dry-run
```

Remove a subscribed source table:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" edit-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --cluster-id 1 --job-id 21 \
  --remove-table old_table \
  --source-db dev_demo \
  --dry-run
```

For a full-task edit, add `--full` to use `updatetransferobjectforfull`.

For an advanced reduce, remap, or processor case, inspect the frontend `Process.vue` payload. Pass exact fragments with `--reduce-config-json`, `--source-schema-without-add-json`, `--target-schema-without-add-json`, `--mapping-without-add-json`, `--processor-without-add-json`, and `--add-processor-config-json`. Or replay the full frontend payload.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-transfer-object \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 21 --payload-json @UpdateTransferObjFO.json --dry-run
```

For an RDB add-table edit, `edit-job` queries source columns and fills `sourceAddConfig` columns. Do not submit an add-table payload with empty source columns.

## Dynamic extras

Before you create an unfamiliar pair, run:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" job-extra-configs \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --source-type mysql --target-type starrocks --defaults
```

Pass returned defaults, or the user's decisions, with `--extra-json`.

## Frontend precheck and queries

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" precheck \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --stage final --payload-json @dataJobData.json

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-simple-jobs \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE"

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-check-tasks \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE"
```

Use `generate-migration-tip --payload-json @file` for the frontend `generateMigrationTip` payload. Use it when partition, clean-target, or edit-mode fields are involved.

When a frontend endpoint has no named command yet, use `call-service`. For that endpoint, record the API row from `audit_frontend_parity.py`. Until you record the row, do not add a wrapper for that endpoint. Use `call-api` only when you have a raw path instead of a frontend service key.
