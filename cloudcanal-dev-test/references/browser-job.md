# Collect Console page evidence

The default acceptance path is [API acceptance](api-job.md). Run the create and screenshot steps below only when the user explicitly asks to use the page. The stop, native readback, and Worker snapshot sections also apply to the default API path.

## When the user asks for the page

When you create a job on the existing version, open the Mini Console the user named and operate it with CUA. When you need to deploy, enter this round's exclusive slot through [Mini release](mini-release.md). Before the wizard, read the protocol, host, and port in the browser address bar. Reuse the session that is already logged in at that entry. Record the real page in the handoff. If the browser stops on a login page, write down the entry and the login step that is still unfinished. Hand a Console login page, SSO, or an identity check to the user.

Take the Mini primary account from `USER_EMAIL` in that slot's private file `~/datasource-lab/cloudcanal-service/private/slot-<NN>/console.env`. Do not reuse an Air account or a default account. The page text `Account not exist` means the account lookup failed. Compare the account you typed with `USER_EMAIL` first. Within the access you already have, do a read-only check that the account configured in that slot's RDP schema exists and is enabled. Keep the original message. Do not retry the password. Use the password only in the private login step.

When you operate the slot through Automation, create that slot's session with `login --base-url "$CONSOLE_ORIGIN" --save-cookie "$SESSION_FILE"`. Pass `--cookie-file "$SESSION_FILE"` on later commands. Use DevTools to keep the page acceptance evidence. Keep the request origin, the result code, and the job id in that evidence. Save the page evidence in this round's own directory.

Fill the wizard in the browser from the acceptance case. Record the source, the target, the subscribed objects, the important settings, and the screenshot for each of those pages. Before the last submit, you can use the Playwright code below. Playwright can attach to an existing Chrome through CDP. Replace `clickSubmit` with the click for this round's real control. `page` is the page where you are filling the wizard. `directory` is the evidence directory you already created.

```js
const fs = require('node:fs/promises');
const path = require('node:path');
const save = (file, data) => fs.writeFile(path.join(directory, file), JSON.stringify(data));
const pageUrl = page.url();
const [response] = await Promise.all([
  page.waitForResponse(r =>
    r.request().method() === 'POST' &&
    new URL(r.url()).pathname === '/cloudcanal/console/api/v1/inner/datajob/create'
  ),
  clickSubmit()
]);
const { code, data: dataJobId } = await response.json();
await save('create.json', {
  pageUrl, requestUrl: response.url(), method: response.request().method(),
  httpStatus: response.status(), code, dataJobId: Number(dataJobId)
});
```

Start the job on the page. If auto-start is already set, watch it start. Open the job you just created from the list. Confirm that the detail matches the expected job name and state, then capture the page URL and a screenshot. When you use raw CDP or the browser developer tools, read those same fields from that page's request and from the detail page. Keep only the listed fields, such as the success code and the id. When you save, drop cookies, the request body, and connection credentials.

```js
await save('detail.json', { pageUrl: page.url() });
await page.screenshot({ path: path.join(directory, 'detail.png') });
```

A CUA screenshot is JPEG, so save it as `detail.jpg` in the format you captured. Keep one detail screenshot in each round's evidence directory.

After the job starts, reload the detail page. Capture the real `queryjob` request URL and the successful response. Save only the fields you need in `query.json`. When you query again with the logged-in CLI, record the real request URL the same way. The example below continues the Playwright session above.

```js
const [query] = await Promise.all([
  page.waitForResponse(r => r.request().method() === 'POST' &&
    new URL(r.url()).pathname === '/cloudcanal/console/api/v1/inner/datajob/queryjob'),
  page.reload()
]);
const { code: queryCode, data: job } = await query.json();
if (!query.ok() || String(queryCode) !== '1') throw new Error('queryjob failed');
const dataTasks = job.dataTasks.map(({dataTaskId, dataTaskType, dataTaskStatus}) =>
  ({dataTaskId, dataTaskType, dataTaskStatus}));
await save('query.json', {requestUrl: query.url(), data: {dataJobId: job.dataJobId, dataTasks}});
```

From the skill directory, run:

```sh
python3 scripts/check_console_jobs.py browser-job "$directory" "$directory/query.json"
```

This command checks that the wizard create, the detail, and the query share one Console origin. It also checks the screenshot format, the job id, the child task ids, and the started state. Then, for each item in the case, review the settings in the screenshots, the full and incremental states, the native target readback, and the counts and detail rows of the separate CHECK. On a failure, report the page you reached, the original message, and the evidence that is still missing.

## Stop a new incremental acceptance job

Stop an incremental job that this round created and started for acceptance after the target readback is done and this round's last incremental check is done. When acceptance ends in a failure, save the failure evidence first, then stop the job. When the user asks to keep the job running, record the job id and the current state.

Stop the job with the Console entry and the job id from the create receipt. Use [`stop-job` in cc-job-operations](../../cloudcanal-console-automation/skills/cc-job-operations/SKILL.md#lifecycle) by default, and click stop on the same detail page when the user asks to use the page. After the stop, reload that same job. Query until `fsmActive=false` and every `INCREMENT` child task is `STOP`. Save the last successful `queryjob` receipt after the stop on its own as `stopped-query.json`. Keep `requestUrl`. Under `data`, keep `dataJobId`, `fsmActive`, and `dataTasks`. On each child task, keep `dataTaskId`, `dataTaskType`, and `dataTaskStatus`. Check the receipt from the skill directory. In the handoff, record the job id, the incremental child task ids, and their states.

```sh
python3 scripts/check_console_jobs.py stopped-test-job --origin "$CONSOLE_ORIGIN" \
  --job-id "$JOB_ID" "$directory/stopped-query.json"
```

When the query or the stop is blocked, record the job id, the last state you saw, and the message. When this round deployed artifacts, hand the slot claim off through [Release and handoff](mini-release.md#release-and-handoff).

## Existing jobs and connection tests

After a package replacement, resume an existing job and check the job id, the child task ids, and the states with `queryjob`. Open the page only when the user asks to use the page. When the job continues an incremental run, record the persisted position from before the stop, and the position or reader state after the resume.

Check the native target readback against this round's case. Record the JARs that actually loaded in the release manifest. Capture a create request only when you create a new job.

When you change only the connection or the driver, save the real Console datasource id, Worker cluster, connection options, and result. When the test server is only protocol-compatible, name the real engine and the scope you verified.

When the user asks to use the page and this round's CHECK is already `COMPLETE`, with the checked row count, the diff count, and the missing row count saved, reopen the detail by the original job id if locating the screenshot times out. Take the extra screenshot read-only. Compare the counts on the page with the saved `query-job` result.

## Compare full and incremental rows

Before the matrix starts, list this round's source-target pairs, full and incremental scope, modes, time zones, and versions to compare. Fill the real results for those same dimensions in the handoff. Write the job id and the child task ids from Console. For each live database component, write the read stage and the write stage it reached. Mark a pair you did not run as not yet verified.

Keep the phase, the case marker or primary key, the expected source value, and the real target value on every readback row. For a LOB or binary column, record the real target type, the NULL state, the length, and the SHA-256 for that case, and keep the native check's exit receipt.

When a case compares full and incremental results, sync one full sample and read it back first. Confirm from that engine's log or status that this job's incremental reader is ready, then write a sample that carries the same business values. On the MySQL binlog protocol, a source `Binlog Dump` connection that belongs to this job can help you confirm that. Judge the incremental end-to-end result by the target readback.

To check a timestamp, read the database's native UTC time, or read epoch seconds. In the TSV, tie the same case together with `full-<case>` and `cdc-<case>`. Record `phase`, `source_utc`, `target_utc`, and `delta_seconds`. When the time text has no explicit offset, convert it to UTC on the query side first. When the case also compares `DATETIME`, add a `datetime_equal` column. `1` means the target value equals the source value.

```sh
python3 scripts/check_console_jobs.py phase-readback "$directory/compare.tsv" --expect correct
python3 scripts/check_console_jobs.py phase-readback "$directory/compare.tsv" --expect same-results
```

`correct` requires both phases' timestamps to equal the source value. `same-results` checks the target timestamp of each sample pair across the two phases. The script compares by instant, and it checks the delta against the values you read back. When you provide `datetime_equal`, both modes check that `DATETIME` equals the source value. When you need to compare two `DATETIME` values that both differ from the source, keep the real values. When both phases fail, still report which row each phase got wrong.

Report in a table. List the phase, the source database, the target database, the real time zone, the job config, the version, the target readback, and the error location. Mark a misconfiguration and a known failing case separately.

## Worker snapshot before release

After you hold the target slot's claim, record `IDLE_CHECK_UTC` as the start of this round's check. Get `CONSOLE_ORIGIN` and the `WORKER` you are about to restart. Capture again even when you publish new artifacts on the claim you already hold. In a Console account that can see every job, query jobs for this Worker. Clear extra filters such as job name, state, and datasource. Capture every page.

Save each successful `listbypage` response on its own as `{requestUrl, workerIp, capturedAt, data}`. Set `requestUrl` to the real HTTP request URL. Set `workerIp` to the Worker filter on the real list request. When the filter is `workerId`, record `workerId` instead of `workerIp`. Set `capturedAt` to the ISO 8601 time and time zone when the response arrived. Keep `allJobCounts` and `jobVos` from the response `data`, and keep the child task and child job fields you need to check job state. An empty list still records the Worker filter you actually used.

For a known job that is not on the list, query it with `queryjob` on the same slot. Store the request URL, the capture time, and `data` in that same shape. Record the same `workerIp` or `workerId` from that job's known Worker assignment. Pass every page and every extra query to the `idle` command in [Mini release](mini-release.md).

## CHECK through the API

Create and query CHECK through the API by default. When the user asks to use the CHECK wizard, wait until the source database selection has taken effect and settled, then select the target database. Recheck the selection, and locate the result by the real database and table.
