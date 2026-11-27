# Accept through the Console API by default

Register datasources, test connections, create jobs, configure them, start them, and query state with [Console automation](../../cloudcanal-console-automation/SKILL.md). Use [page evidence](browser-job.md) only when the user asks to use the page.

Confirm this round's Console origin, the Automation session for the same slot, and the Worker cluster. For an unfamiliar source-target pair, check the request against the frontend source, the types, the service definitions, and the dynamic WebOp. Then dry-run the request. Do not open the wizard or capture a browser request before that dry-run.

After you create the job, read back the config, the subscription, and the mapping that were saved. Start the job only after async creation succeeds. When `fsmActive=false` and `dataTaskState=INIT`, activate the FSM for the first time with `continue-job` in [Lifecycle](../../cloudcanal-console-automation/skills/cc-job-operations/SKILL.md#lifecycle). When `BUILD_STRUCT` exists, that task must be `COMPLETE`. A new job that did not select structure migration still needs this activation.

Before that first activation, `currTaskStatus` can be `UNKNOWN`, and an ordinary `start-job` then reports `current task id empty`. Use an ordinary start only to resume a job that was activated and later stopped. Query until the child tasks that do the work have started.

Save `create.json` and the post-start `query.json` in this round's evidence directory. Take the fields from the real API request and the successful receipt, and drop cookies, credentials, and request bodies you do not need.

`create.json` keeps `requestUrl`, `method`, `httpStatus`, `code`, and the `dataJobId` returned by the API. For example:

```json
{"requestUrl":"http://<this-round-host>:<port>/cloudcanal/console/api/v1/inner/datajob/create","method":"POST","httpStatus":200,"code":"1","dataJobId":123}
```

`query.json` keeps the real `queryjob` `requestUrl`, and under `data` it keeps `dataJobId`, `fsmActive`, and `dataTasks`. Each child task keeps `dataTaskId`, `dataTaskType`, and `dataTaskStatus`. When you need a CHECK freshness check, also keep the completion time and the counts.

```sh
python3 scripts/check_console_jobs.py api-job "$directory" "$directory/query.json"
```

This check only confirms the same origin, the created id, and the real started state. A started job does not mean the data is right. For a full load, read back the prepared sample. For incremental, confirm that this job's reader is ready, then write a change with a unique marker, and read it back through the target's own entry. For binary data, check the real bytes, the length, and the hash, and record the full result and the incremental result as separate cases.

Use the same shared checks after that:

- [Stop a new incremental acceptance job](browser-job.md#stop-a-new-incremental-acceptance-job), and save the `stopped-test-job` receipt.
- [Compare full and incremental rows](browser-job.md#compare-full-and-incremental-rows), save the native readback, and run `phase-readback` when you need it.
- [Worker snapshot before release](browser-job.md#worker-snapshot-before-release), capture the full pages and the extra query receipts through the API, then run `idle`.
- For CHECK, run `fresh-check` by job id, and check this round's completion time, checked row count, diff count, and missing row count.

In the handoff, write the real entry, the job id, the child task ids, the API state, the target readback, the state after the stop, and anything still unfinished. The default path does not need a page screenshot.
