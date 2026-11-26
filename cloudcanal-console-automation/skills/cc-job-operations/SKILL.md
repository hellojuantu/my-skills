---
name: cc-job-operations
description: Operate CloudCanal jobs, config, schedules, and positions through the Console API. Use for start, stop, retry, config repair, and position changes, not for creating datasources.
---

# Job operations

Resolve the console URL, cookie, and object ids before you run these commands.

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

Use `continue-job` only for the post-structure state the frontend handles with `fsmStart`. Structure migration is complete, `fsmActive=false`, and the full or increment tasks are still waiting. For ordinary lifecycle work use `start-job`, `stop-job`, `restart-job`, or `replay-job`.

Run these commands against the existing slot's Console. They do not read or release a slot claim. For a deployment and its handoff, follow the [Mini release workflow](../../../cloudcanal-dev-test/references/mini-release.md).

## FSM and delete cleanup

The frontend has a separate system FSM page. When a job or check child cannot be deleted because its FSM is still active, do not guess paths such as `inactivefsm` or `stopfsm`. Use the wrapped FSM page endpoints.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-fsm \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 82

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" inactivate-fsm \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 82
```

When the user asks for cleanup, prefer one command. It handles child jobs first. It ignores a harmless "not running" stop error. It inactivates the FSM when needed. It waits briefly for `WAIT_START` or `RUNNING` tasks to leave the states that block delete. Then it deletes.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" delete-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 81 --delete-children --stop-first --inactivate-fsm
```

This matters for check child jobs after a CloudCanal check replay. `WAIT_START` is a normal scheduler state. It is not a cue to call `activefsm` again. If deletion still fails, query `query-fsm --job-id JOB_ID`. Also query `query-job --job-id JOB_ID`. Report the backend error with the FSM id and the current task status.

## Logs

Tail a task log. Resolve the task id from job state. Or pass `--task-type`.

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

`--contains` filters matching log lines. It does not filter whole files. Use it for a quick `ERROR` check.

Async console job logs and retry:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" query-console-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --console-job-id 100 --summary

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" operate-console-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --action retry --console-job-id 100 --console-task-id 200 --dry-run
```

Use this for create-job async failures such as `init TiDB CDC`, `CreateFSM`, or scheduler tasks. The summary prints failed console task ids so the retry hits the same frontend endpoint.

## Configs

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" get-job-config --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-job-config-tags --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE"
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-job-configs --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --config-name host
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-job-configs --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --config host:SOURCE:DATASOURCE:db.internal:3306 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" export-job-config --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --dry-run
```

Use `job-config-template --preview` before you apply a template.

### Repair copied datasource configs

A data job stores a snapshot of datasource connection information. If you edit a datasource after the job was created, the existing job still uses the old copied values. List each affected name. Check the saved value, endpoint, and config type.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-job-configs \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 21 --config-name host
```

Update only the affected job entries. Use `NAME:END_POINT_TYPE:CONFIG_TYPE:value` with the saved entry's `endPointType` and `configType`. For a source host those are `SOURCE` and `DATASOURCE`. Get `--tag` filters from `list-job-config-tags`.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-job-configs \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --job-id 21 \
  --config host:SOURCE:DATASOURCE:tidb-sql.internal:4000 \
  --config pdHost:SOURCE:DATASOURCE:tidb-pd.internal:2379 \
  --config password:SOURCE:DATASOURCE: \
  --dry-run
```

After the config update, retry the failed async console task.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" operate-console-job \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --action retry --console-job-id 100 --console-task-id 200
```

If the job failed before or during creation, and the test data was initialized against the old endpoint, choose one option. Reinitialize the temporary source or target namespace on the new endpoint before you retry. Or delete the job. Then create it again. Retrying the async task repairs configuration. It does not move old schemas, topics, indexes, or files between hosts.

## Positions

Query the dynamic position form first.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" position-ops \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --task-id 123 --job-id 21
```

Fetch, update, or reset:

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

## Follow-up jobs

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" can-add-revise-task --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" add-revise-task --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" add-check-child-job --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --payload-json @check-child.json --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" attach-incre-task --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --dry-run
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" detach-incre-task --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" --job-id 21 --dry-run
```

For a frontend endpoint that is not wrapped yet, use `call-service --service SERVICE --payload-json @payload.json --dry-run`. Use `call-api --path PATH` when you only have the raw DevTools URL. `--set jobId=21` parses JSON scalars, so numbers and booleans stay typed.
