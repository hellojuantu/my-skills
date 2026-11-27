---
name: cc-frontend-parity
description: Build automation parameters from CloudCanal frontend requests and engine-specific cases. Use for an unverified datasource pair or request body.
---

# Frontend parity notes

The frontend source is the contract for payload shape. From the CloudCanal workspace root, set the frontend checkout for this session.

```bash
export CLOUDCANAL_WEB_DIR="$(cd clouddm-web && pwd -P)"
```

For a standalone frontend checkout, pass its path with `--frontend-dir`.

`clouddm-web` contains both CloudCanal and ClouDDM UI code. This skill covers CloudCanal console automation only. Include `/cloudcanal/...` service paths and the CloudCanal datasource-management `/rdp/...` paths from `datasource.js` and `constant.js`. Ignore `/clouddm/...` services and unrelated RDP account, SaaS, and system APIs.

Primary files:

- `src/components/function/mixin/createJobMixin.js` builds create-task `sourceSchema`, `targetSchema`, `mappingDef`, and processor config.
- `src/views/data/Process.vue` is the edit-subscription payload, including `addMappingConfig`, `sourceAddConfig`, `targetAddConfig`, and the without-add configs.
- `src/views/dataSource/AddDataSource.vue` is the RDP datasource add multipart parts and datasource-specific security fields.
- `src/views/dataSource/DataSource.vue` is the datasource update for description, account, AKSK, host, and delete.
- `src/services/http/api/dataJob.js`, `datasource.js`, `webOp.js`, and `fsm.js` hold endpoint path constants.
- `src/views/dataSourceGroup.json` holds groups such as `mq`, `hasSchema`, `noDb`, `redis`, `es`, and `noColumn`.

## Audit script

Before you say the skill matches a frontend checkout, run:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/audit_frontend_parity.py" \
  --frontend-dir "$CLOUDCANAL_WEB_DIR" \
  --format markdown

python3 "$CLOUDCANAL_SKILL/scripts/audit_frontend_datasource_types.py" \
  --frontend-dir "$CLOUDCANAL_WEB_DIR" \
  --format markdown
```

The datasource type audit compares frontend types with the types the Console CLI recognizes.

For the narrower datasource, job, and operation surface in `audit_frontend_parity.py`, add `--core`. The default audit scans every `src/services/http/api/*.js` file. It reports CloudCanal `/cloudcanal` service paths and CloudCanal datasource `/rdp` paths. CloudCanal log, worker, monitor, cluster, auth, and related page APIs stay visible. ClouDDM endpoints stay out.

Read the labels this way.

- `wrapped` means the endpoint has a named Python command or helper.
- `call-service` means you can call the endpoint by frontend service key, but not yet by a named command.
- `intentional-not-wrapped` means a manual FSM activation endpoint. Do not expose these as normal operations.

When a `call-service` row becomes a common workflow, read the frontend payload. When that row becomes a common workflow, add a named command. Until then, use the frontend service key.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-services \
  --frontend-dir "$CLOUDCANAL_WEB_DIR" --filter queryjob

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" call-service \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --service ccDataJobQueryJob \
  --set jobId=21 --dry-run
```

If duplicate service keys exist, pass `--api-file fileName.js`. If you already have a raw path from DevTools, use `call-api --path ...`.

For a multipart frontend API, use `--multipart` plus `--json-part NAME=@payload.json`, `--part NAME=value`, or `--file-part NAME=/path/to/file`. If the backend expects a single JSON text part, set `--payload-part-name` to the frontend field name.

Frontend `$services` defaults to POST with JSON data. If a call overrides the method or the response type, match it.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" call-service \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --service ccDataJobConfigExport \
  --set dataJobId=21 --set exportType=EXCEL \
  --response raw --output /tmp/datajob-config.xlsx
```

Use `--method GET` for a service called with `method: 'get'`. Use `--response text` for plain text. Use `--response raw --output FILE` for a blob or download. Use `--header X-Product-Code=...` when a SaaS or product-cluster page relies on a product header the frontend injects.

## Datasource groups

Do not hardcode a decision from the product name alone. The automation mirrors the current `dataSourceGroup.json` groups.

- MQ: Kafka, AutoMQ, AmazonMSK, RocketMQ, RabbitMQ, Pulsar.
- Redis: Redis, ElastiCache.
- ES: ElasticSearch.
- hasSchema: Oracle, PostgreSQL, Hana, SQL Server, Db2, Tunnel, Hudi, file-like sources, and related PostgreSQL-compatible families.
- noDb: Kudu, MQ, Redis, ElasticSearch, RagApi, DynamoDB.

`RagApi` uses `TABLE_TOPIC` for target mapping. It belongs to `noDb`, `noStruct`, and `noColumn`. For an LLM provider such as OpenAI, DashScope, or Bedrock, read the datasource settings from the frontend request or from the dynamic KV definitions.

For Hive, Hudi, Iceberg, Paimon, DeltaLake, Kudu, MaxCompute, and DataLakeFormation, use the catalog, table, partition, and sink options the frontend exposes for the selected engine.

When frontend groups change, update the Python constants before you claim parity.

## Datasource config parity

Datasource create and update APIs, and data job create APIs, do not share one payload lifetime. Datasource management saves the reusable datasource object. Data job creation copies selected connection fields and dynamic config into the task. Check both surfaces when a datasource-specific setting is involved.

Trace these dynamically. Or query these dynamically.

- A TiDB source needs the SQL host and the PD host copied into the job. Fixing the datasource host alone does not fix an existing TiDB-source job.
- StarRocks, Doris, and SelectDB need HTTP, FE, and BE address fields copied when the frontend includes them.
- Kafka and other MQ sources may use `ANY_DB` or topic mapping plus source-specific WebOp fields.
- Secret fields may be masked on query. A repair flow needs credentials the user provides, or a captured frontend payload.

For a failed async create, use `list-job-configs --config-name NAME` for each affected field. Identify the job entry by `endPointType` and `configType`. Compare its saved value with the datasource detail. If the saved values differ, repair the job copy. If the saved values differ, retry the console task. If test data was initialized on the old endpoint, recreate the dataset. If test data was initialized on the old endpoint, reinitialize the dataset instead.

## Create-job shape checks

Dry-run these fields. Inspect these fields.

- A normal DB target usually has `targetSchema: null`.
- An MQ source to a normal DB target has a target DB schema and `ANY_DB`.
- An MQ source to a hasSchema target has a target DB and schema, and `ANY_SCHEMA`.
- A Redis target uses target schema entries like `{ "prefix": "...", "suffixFields": [] }`.
- An ES target uses `{ "indexName": "...", "fields": [], "idFieldNames": [] }`.
- `COLUMN_COLUMN` is present for DB-source branches even when no explicit column mappings are set.

## When to verify the request contract

Inspect frontend source, types, service definitions, and dynamic WebOp when the request involves any of these. Compare the resulting request in dry-run. Use a browser only when the user explicitly requests page operation.

- A complex edit-subscription reduce or remap.
- Table-level partition expressions, Hive partition settings, Greptime time indexes, or StarRocks, Doris, and SelectDB partition details.
- LLM or RagApi processors, virtual columns, implicit columns, or a custom package processor.
- A datasource type or source-target pair that has not been dry-run compared yet.

Build the verified payload from those contracts and pass it through `--*-json @file`, or update the automation. An existing captured request can also be replayed; a new browser capture is optional.
