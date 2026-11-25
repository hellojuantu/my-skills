---
name: cc-frontend-parity
description: Build automation parameters from CloudCanal frontend requests and engine-specific cases. Use for an unverified datasource pair or request body, not for running a batch.
---

# Frontend Parity Notes

The frontend source is the contract for payload shape. From the CloudCanal workspace root, set the frontend checkout for this session.

```bash
export CLOUDCANAL_WEB_DIR="$(cd clouddm-web && pwd -P)"
```

For a standalone frontend checkout, pass its path with `--frontend-dir`.

`clouddm-web` contains both CloudCanal and ClouDDM UI code. This skill only targets CloudCanal console automation: include `/cloudcanal/...` service paths and the CloudCanal datasource-management `/rdp/...` paths from `datasource.js` and `constant.js`; ignore `/clouddm/...` services and unrelated RDP account/SaaS/system APIs.

Primary files:

- `src/components/function/mixin/createJobMixin.js`: create-task `sourceSchema`, `targetSchema`, `mappingDef`, processor config assembly.
- `src/views/data/Process.vue`: edit subscription payload, `addMappingConfig`, `sourceAddConfig`, `targetAddConfig`, without-add configs.
- `src/views/dataSource/AddDataSource.vue`: RDP datasource add multipart parts and datasource-specific security fields.
- `src/views/dataSource/DataSource.vue`: datasource update desc/account/AKSK/host/delete calls.
- `src/services/http/api/dataJob.js`, `datasource.js`, `webOp.js`, `fsm.js`: endpoint path constants.
- `src/views/dataSourceGroup.json`: datasource groups such as `mq`, `hasSchema`, `noDb`, `redis`, `es`, `noColumn`.

## Audit Script

Before saying the skill is aligned with a frontend checkout, run:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/audit_frontend_parity.py" \
  --frontend-dir "$CLOUDCANAL_WEB_DIR" \
  --format markdown

python3 "$CLOUDCANAL_SKILL/scripts/audit_frontend_datasource_types.py" \
  --frontend-dir "$CLOUDCANAL_WEB_DIR" \
  --format markdown
```

For the narrower datasource/job/operation surface, add `--core`. The default audit scans every `src/services/http/api/*.js` file but only reports CloudCanal-relevant `/cloudcanal` service paths plus CloudCanal datasource `/rdp` paths, so CloudCanal log, worker, monitor, cluster, auth, and related page APIs remain visible without pulling in ClouDDM endpoints.

Interpretation:

- `wrapped`: the endpoint has a named Python command or helper.
- `call-service`: the endpoint is callable by frontend service key, but not yet by a named command.
- `intentional-not-wrapped`: manual FSM activation endpoints; do not expose these as normal operations.

For `call-service` rows that become common workflows, inspect the frontend payload and add a named command. Until then, use the frontend service key:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-services \
  --frontend-dir "$CLOUDCANAL_WEB_DIR" --filter queryjob

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" call-service \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --service ccDataJobQueryJob \
  --set jobId=21 --dry-run
```

If duplicate service keys exist, pass `--api-file fileName.js` to disambiguate. If you already have a raw path from DevTools, use `call-api --path ...`.

For multipart frontend APIs, use `--multipart` plus `--json-part NAME=@payload.json`, `--part NAME=value`, or `--file-part NAME=/path/to/file`. If the backend expects a single JSON text part, set `--payload-part-name` to the frontend field name.

Frontend `$services` defaults to POST with JSON data. If a call overrides method or response type, mirror it:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" call-service \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --service ccDataJobConfigExport \
  --set dataJobId=21 --set exportType=EXCEL \
  --response raw --output /tmp/datajob-config.xlsx
```

Use `--method GET` for services called with `method: 'get'`, `--response text` for plain text, `--response raw --output FILE` for blob/download APIs, and `--header X-Product-Code=...` when a SaaS/product-cluster page relies on frontend-injected product headers.

## Datasource Groups

Do not hardcode based only on product names. The automation mirrors the current `dataSourceGroup.json` groups for common decisions:

- MQ: Kafka, AutoMQ, AmazonMSK, RocketMQ, RabbitMQ, Pulsar.
- Redis: Redis, ElastiCache.
- ES: ElasticSearch.
- hasSchema: Oracle/PostgreSQL/Hana/SQLServer/Db2/Tunnel/Hudi/file-like and related PG-compatible families.
- noDb: Kudu, MQ, Redis, ElasticSearch, RagApi, DynamoDB.

Frontend routing is not the same as local test-data readiness. `RagApi` maps like a topic target in create-job payloads (`TABLE_TOPIC`) and is `noDb/noStruct/noColumn`; LLM providers such as OpenAI/DashScope/Bedrock are datasource/config surfaces, not generic CloudCanal table stores. Do not invent a `/collections` or generic HTTP CRUD contract for them. Capture the frontend request or datasource kv contract, then add a dedicated adapter before exposing any named data-test behavior.

Hive/Hudi/Iceberg/Paimon/DeltaLake/Kudu/MaxCompute/DataLakeFormation have catalog/table semantics and frontend-specific settings such as partition, table type, and sink options. Do not represent them with local JSONL files unless the datasource being tested is explicitly a file object source. Keep them routed but not local-data ready until a native adapter for the actual engine is implemented.

When frontend groups change, update the Python constants before claiming parity.

## Datasource Config Parity

Datasource create/update APIs and datajob create APIs do not have identical payload lifetimes. Datasource management saves the reusable datasource object; datajob creation copies selected connection fields and dynamic config into the task. Always check both surfaces when a datasource-specific setting is involved.

Examples that must be traced or queried dynamically:

- TiDB source needs the SQL host and PD host copied into the job. A datasource host fix alone will not fix existing TiDB-source jobs.
- StarRocks/Doris/SelectDB need HTTP/FE/BE address fields copied when the frontend includes them.
- Kafka and other MQ sources may use special `ANY_DB`/topic mapping plus source-specific WebOp fields.
- Secret fields may be masked on query, so a repair flow needs explicit user-provided credentials or a captured frontend payload.

For a failed async create, use `list-job-configs --config-name NAME` for each affected field. Identify the job entry by `endPointType` and `configType`, then compare its saved value with the datasource detail. If the saved values differ, repair the job copy and retry the console task. If test data was initialized on the old endpoint, recreate or reinitialize the dataset.

## Create-Job Shape Checks

Dry-run and inspect these fields:

- Normal DB target usually has `targetSchema: null`.
- MQ source to normal DB target has target DB schema and `ANY_DB`.
- MQ source to hasSchema target has target DB/schema and `ANY_SCHEMA`.
- Redis target uses target schema entries like `{ "prefix": "...", "suffixFields": [] }`.
- ES target uses `{ "indexName": "...", "fields": [], "idFieldNames": [] }`.
- `COLUMN_COLUMN` is present for DB-source branches even when no explicit column mappings are set.

## When To Trace The Browser

Use the frontend directly or browser automation when the request involves:

- Complex edit subscription reduce/remap flows.
- Table-level partition expressions, Hive partition settings, Greptime time indexes, StarRocks/Doris/SelectDB partition details.
- LLM/RagApi processors, virtual columns, implicit columns, or custom package processors.
- A datasource type or source-target pair not already dry-run compared.

Capture the frontend request payload, then either pass it through `--*-json @file` or update the automation.
