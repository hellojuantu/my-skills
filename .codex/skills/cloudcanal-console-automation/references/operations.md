# Job Operations

Use the operation commands after resolving the console URL, cookie, and object ids.

## Lifecycle

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" start-job --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" continue-job --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" stop-job --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" restart-job --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" replay-job --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21
```

Batch:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" operate-jobs \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --action restart --job-id 21,22 --dry-run
```

Use `continue-job` only for the same post-structure state the frontend handles with `fsmStart`: structure migration is complete, `fsmActive=false`, and full/increment tasks are still waiting. For ordinary lifecycle work use `start-job`, `stop-job`, `restart-job`, or `replay-job`.

## FSM And Delete Cleanup

The frontend has a separate system FSM page. When a job or check child cannot be deleted because its FSM is still active, do not guess datajob paths such as `inactivefsm` or `stopfsm`. Use the wrapped FSM page endpoints:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-fsm \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 82

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" inactivate-fsm \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 82
```

For cleanup requested by the user, prefer one command that handles child jobs first, ignores harmless "not running" stop errors, inactivates FSM when needed, waits briefly for `WAIT_START`/`RUNNING` tasks to leave the backend delete-blocked states, then deletes:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" delete-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 81 --delete-children --stop-first --inactivate-fsm
```

This is especially important for check child jobs after CloudCanal check replay. `WAIT_START` is a normal scheduler state, not a cue to call `activefsm` again. If deletion still fails, query `query-fsm --job-id JOB_ID` and `query-job --job-id JOB_ID`, then report the backend error with the FSM id and current task status.

## Logs

Task log tail, with task id resolved from job state or `--task-type`:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" tail-task-log \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 21 --task-type INCREMENT --text

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" tail-task-log \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 21 --task-type FULL --contains ERROR --text
```

Worker and operation logs:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" tail-worker-log \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --worker-id 1 --log-type WORKER_MAIN_LOG --contains ERROR --text

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" grep-operation-log \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --operation-id 12345
```

`--contains` filters matching log lines, not whole files, so it is suitable for quick `ERROR` checks.

Async console job logs and retry state:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" query-console-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --console-job-id 100 --summary

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" operate-console-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --action retry --console-job-id 100 --console-task-id 200 --dry-run
```

Use this for create-job async failures such as `init TiDB CDC`, `CreateFSM`, or scheduler tasks. The summary prints failed console task ids so the retry can target the same frontend endpoint.

## Configs

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" get-job-config --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-job-config-tags --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE"
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-job-configs --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --config-name host
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-job-configs --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --config host:SOURCE:DATASOURCE:db.internal:3306 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" export-job-config --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --dry-run
```

Use `job-config-template --preview` before applying a template.

### Repair Copied Datasource Configs

Datajobs store a snapshot of datasource connection information. If a datasource is edited after a job was created, the existing job still uses the old copied values. List each affected name and check the saved value, endpoint and config type.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-job-configs \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 21 --config-name host
```

Update only the affected job entries. Use `NAME:END_POINT_TYPE:CONFIG_TYPE:value` with the saved entry's `endPointType` and `configType`. For a datasource field such as a source host, these are `SOURCE` and `DATASOURCE`. Get available `--tag` filters from `list-job-config-tags`.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-job-configs \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 21 \
  --config host:SOURCE:DATASOURCE:tidb-sql.internal:4000 \
  --config pdHost:SOURCE:DATASOURCE:tidb-pd.internal:2379 \
  --config password:SOURCE:DATASOURCE: \
  --dry-run
```

After applying the config update, retry the failed async console task:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" operate-console-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --action retry --console-job-id 100 --console-task-id 200
```

If the job failed before or during creation and the test data was already initialized against the old datasource endpoint, reinitialize the temporary source/target namespace on the new endpoint before retrying, or delete and recreate the job for a clean test. Retrying only the async task repairs configuration; it does not move old test schemas, topics, indexes, or files between database hosts.

## Positions

Query dynamic position form options first:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" position-ops \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --task-id 123 --job-id 21
```

Fetch/update/reset:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" fetch-current-pos --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --task-id 123 --pos-type MYSQL_LOG_FILE_POS
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-incre-pos --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --task-id 123 --pos-type MYSQL_LOG_FILE_POS --journal-file mysql-bin.000001 --file-position 4 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" reset-position --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --task-id 123 --reset-time-millis 1781200000000 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" reset-pos-to-current --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --task-id 123 --pos-type MYSQL_LOG_FILE_POS --dry-run
```

## Scheduling

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" time-schedule --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --action pause --job-id 21 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" manual-schedule --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --data-task-id 1001 --old-worker-id 1 --target-worker-id 2 --dry-run
```

## Follow-Up Jobs

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" can-add-revise-task --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" add-revise-task --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" add-check-child-job --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --payload-json @check-child.json --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" attach-incre-task --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" detach-incre-task --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --dry-run
```

For frontend endpoints not yet wrapped, prefer `call-service --service SERVICE --payload-json @payload.json --dry-run`; use `call-api --path PATH` when you only have the raw DevTools URL. `--set jobId=21` parses JSON scalars, so numbers and booleans remain typed.
