---
name: datasource-lab
description: Install and maintain CloudCanal test databases on Mini through MotherData first, record a temporary manual instance only when no template fits, check databases and disks, and connect verified datasources to CloudCanal slots.
---

# Datasource Lab

Enter `~/datasource-lab` with `MINI_SSH_HOST` from `mini.env`. This directory holds the ledger, full snapshots, the published usable list, and check records. Install every new CloudCanal test database on Mini. Put one-off reproductions and temporary containers there too. When SSH asks for an identity check, continue at [Mini SSH identity check](../cloudcanal-dev-test/skills/cc-setup/SKILL.md#mini-ssh-identity-check).

Look at existing MotherData installs and usable templates first. Reuse a verified instance when the version, the architecture, and the case all match. Install in MotherData when a template fits. If an earlier install failed, find the cause first.

Install by hand on Mini only when no template fits. In the Lab ledger, record the missing template, the temporary use, and what should later move into MotherData.

Checks cover instances MotherData hosts and manual instances recorded in the Lab. When you connect one to CloudCanal, record each slot's datasource id and the Worker connection result.

## Manual install on Mini

From this skill directory, run `python3 scripts/check-deployment-route.py http://mini:8765 <engine>`. Take the host name from `mini.env`. When that name is not `mini`, use it in the URL.

Exit code `1` means use the MotherData template in the output. Exit code `0` is the only path into the temporary manual install. Exit code `2` means fix the directory or the arguments first.

Add `--exact-image image:tag` only when the case requires that image. When a template install fails, check the node, the install conditions, or the resources from the original record.

1. Deploy the required version and configuration on Mini with `ssh mini`.
   Before you start that instance, check the test instances, ports, and disk already on Mini.
   Datasource Lab manages an instance you deploy this way.
2. Record a stable `labRecord` under `instances` in `host-locations.json`.
   Record the engine, version, install host, access endpoint, container or service name, purpose, and acceptance evidence.
   Include a temporary instance, with its lifetime and cleanup state.
   Store connection credentials in `private/connections.local.json` with mode `0600`, linked by the same `labRecord`.
3. Test the connection and the reads and writes the case needs.
   To attach the instance to CloudCanal, register it on an authorized slot and test the Worker.
   Use the Lab record for a manual instance.
   Keep a MotherData id for an instance that MotherData hosts.

## Create and maintain MotherData databases

The MotherData home page is `http://mini:8765/`. The service directory is `~/datasource-lab/motherdata-service/`.

To upgrade the application, lock the Gitee `master` commit in [Publish master to Mini](skills/lab-motherdata-deploy/SKILL.md). Prove Flyway on an isolated test copy. Switch only after Flyway passes on that copy. Do not create a rollback backup unless the user asks.

MotherData metadata lives in the `motherdata` database on the shared MySQL. Each publish switches one service.

From this skill directory, run `python3 scripts/check-service.py http://mini:8765`. Check health, nodes, install records, and datasource ids. Compare the same records before and after the deploy. Open the Mini home page.

In MotherData, choose the Mini node, database type, driver, architecture, and port. Check installs that already exist before you add one. When you take over an instance, keep its data and confirm the install host. Order resident databases by the link priority you were given and by the verified list. After the install, test the real connection and the reads and writes. Then record the instance in the Lab. Before you uninstall a database, or before you remove volumes and images, ask the user to confirm the exact objects.

## Record MotherData connections

After you install, take over, or change a connection, update `private/motherdata-connections.local.json` on Mini from MotherData. This file holds the private connection records for every engine. Its mode is `0600`. It is a JSON array with one entry per instance.

Each entry has these fields: `id`, `scope`, `motherDataInstallId`, `type`, `host`, `port`, `database`, `user`, `password`, and any TLS fields the instance needs. `id` is the MotherData datasource id. `scope` is `motherdata`. `user` and `password` are the fixed test account.

`host-locations.json` records the install location, the access endpoint, and the stable id. Keep accounts, passwords, and keys in the private file on Mini. Check reports and this skill repo use redacted fields only.

To sync a fixed account, find the install record by MotherData datasource id. Read the current credentials from **Get connection info**. Match the Lab ledger and each slot registration by that same id. Run a Worker connection test on each slot. Record the result. Use credentials only in a private session or process.

When a case needs its own account, confirm the account and its privileges on the MotherData instance that hosts it. Under that same Lab instance, add a `testAccounts` entry with its own id, purpose, target database, account, and password. Record the CloudCanal slot and datasource id you actually used. The special account keeps the original MotherData instance id. CloudCanal gets its own registration. Test that registration through the slot's Worker.

Fixed-account fields are for resident registration and the default check. Start from the full list of MotherData datasource ids. Put each instance of the same engine on its own row. Match the Lab ledger and every CloudCanal slot registration, one id at a time. Record the matching datasource id, anything missing, and the connection result.

On the CloudCanal side, prefer an id map you already have. With no map, match the engine, the endpoint, the service or database name, and the account. `commonDefaults` only chooses which instance a common link prefers. A full sync fills in each missing entry. Keep a failed connection in the report. Keep an entry that is not verified yet.

## CloudCanal slot connection check

After you add a datasource, publish, or run a full sync, run **Test Connection** through the Console API. Cover each regular registration on the slots and instances in the round. Use the page only when the user asks for a page action.

In the API parameters, select the Worker cluster and network entry for that registration. Keep the real API response. Link evidence for a manual instance by `labRecord`. Check a dedicated account or an extra registration against its own test case. This result covers only the connection you selected. For a data sync, read the target back on that job.

Collect a full `motherdata.json` from MotherData on its own. Write the round start time, each slot's expected Worker cluster, and the regular registrations into `expected.json`.

Each item in `results` in the default `evidence.json` includes `requestUrl`, `instanceId`, `cluster`, `status`, and `testedAt`. `testedAt` includes a timezone. `requestUrl` is the real `/cloudcanal/console/api/v1/inner/datasource/connection` request.

When the Worker API response says the connection succeeded, set `status` to `Successful`. Keep the redacted raw API evidence. When the user asks for a page check, save `pageUrl` and pass `--evidence-kind browser` to the check command. The three files use redacted fields only.

By default, check every MotherData datasource on 8111 and 8112. For one slot, read `consolePort` from [Mini slot registration](../cloudcanal-dev-test/references/mini-release.md) and pass it to `--slot`.

Pass one `--source-id` for each datasource under test. List that registration on the slot in `expected.json`. Pass `labRecord` for a manual instance. When you check only manual instances, `dataSources` in the MotherData export can be empty.

The example below checks two datasources that were added only on 8111.

```json
{"notBefore":"2026-11-23T09:00:00Z","slots":{"8111":{"cluster":"Default Cluster","sources":{"5":"ora-26ai","6":"ora-19c"}}}}
```

```sh
python3 scripts/check-service.py http://mini:8765 > motherdata.json
python3 scripts/check-slot-connections.py motherdata.json expected.json evidence.json --slot 8111 --source-id 5 --source-id 6
```

Every instance under test on every slot in the round needs a Worker `Successful` result from this round.

`check-slot-connections.py` checks ids against the full catalog. It then checks the selected range for Console API source, registration, Worker cluster, result, and time.

When a result is missing or failed, keep the original message for that slot and instance. Update the check status from what you measured.

## Weekly datasource check

The scheduled job runs [Datasource Lab weekly check](skills/lab-weekly-check/SKILL.md) at 9:00 on Monday morning. Put datasources, Worker results, disk, and orphan resources in one [Mini CHECK report](references/check-report.md).

The CHECK phase uses read-only probes and archives the evidence. Console **Test Connection** on a registered relational database can update datasource version metadata. Run that during publish or registration acceptance. Before you act, get the user's confirmation by report item number.

1. Read these files on Mini: `README.md`, `host-locations.json`, `private/motherdata-connections.local.json`, `private/connections.local.json`, `private/datasources-247.local.json`, and `private/health-checks/latest.json`.
   From `host-locations.json`, check Mini manual instances that are still in use.
   Look up private connections by `labRecord`.
   For old Air candidates, use `Air` scope records in `private/datasource-locations.json` on Mini.
   A full snapshot includes every candidate in each scope.
   Include a source that was down last time.
   Keep the existing scope and id.
   Keep the Lab record id for a manual instance.
   Merge probes that test the same thing.
   Map each result back onto the snapshot.
2. In the ledger, record the install host, access endpoint, probe host, and evidence time as separate fields.
   For an old endpoint that still forwards through Air, follow the current config to the upstream host or container.
   When you only see a listening port, mark the install location as not verified yet.
   Record the physical host for a LAN instance too.
   Measure Mini containers and Worker reachability from Mini.
   Test a loopback service on the host that runs it.
3. Read the account and the named database from the archived connection record.
   With a driver from Mini `private/health-venv`, or an existing native client, run the smallest authenticated read.
   For MySQL, PostgreSQL, and SQL Server, select the target database and run `SELECT 1`.
   For Oracle, connect with the registered service name and run `SELECT 1 FROM DUAL`.
   For HANA, run `SELECT 1 FROM DUMMY`.
   For MongoDB and Redis, run an authenticated ping.
   For Elasticsearch, read cluster health.
   For Catalog, list namespaces.
   For Kafka, read broker metadata.
   When you reuse `probe_connections.py` on Mini, import `probe`.
   Do not call the command entry. That entry overwrites the published list.
   To probe Oracle with `probe`, join the ledger host, port, and service name as `host:port:service`.
   Pass that value as `privateHost`.
   Some drivers connect only to the default database, so also check the database named in the record.
   Keep these classes separate: port open, missing driver, permission error, not tested, and plain files.
   Retry a transient network error only a limited number of times.
4. On each run, create a private archive under `private/health-checks/`, named with the UTC time.
   Archive the full candidate file for each scope before you probe.
   Start every probe from that archive.
   In `summary.snapshotSha256ByScope`, record the SHA-256 of each scope's archive file.
   Keep each result, its start and end times, and its retry count.
   Also keep the install location, the test location, the last published version, and this round's difference.
   Summarize pass, fail, recovered, not tested, and the reason, grouped by host.
   After the check is complete, update `latest.json` atomically.
   Full snapshots and credentials stay in the lab.
   The weekly report lists only the redacted evidence it needs.
5. The proposed usable list includes only candidates that passed this probe and are still enabled.
   Mark entries to remove, and entries to add back after they recover.
   Check slot registrations for MotherData instances and for manual instances still in use.
   Cite an existing Worker result, and note when it was tested.
   When this round has no slot evidence, mark the entry not tested this round.
   Finish this round's [Disk, images, and cleanup](#disk-images-and-cleanup) check.
   Keep the source snapshots and the older lists.
   For a publish, a config repair, or a cleanup, wait for the user to confirm each report item.
   After that confirmation, check that the ledger still matches the snapshot.
   Probe again any record whose connection address, target database, or auth config changed.
   Publish atomically from the snapshot you already have, then check the ids and the count.
   When the user asks for a backup, follow [Backups](../cloudcanal-dev-test/references/backups.md).

You can run the read-only comparison from the skill directory on Air or Pro. Replace `RUN_UTC` with the real archive directory name. Compare full coverage and the snapshot summary for each scope. Print the ids to add and the ids to remove. Retired and disabled marks come from the ledger. A historical report with no snapshot summary can show candidate differences only with `--historical`. A publish needs a new probe. Write the report against that snapshot.

```sh
ssh -o BatchMode=yes mini 'cd ~/datasource-lab && /usr/bin/python3 - private/health-checks/RUN_UTC/datasources-247.json private/usable-datasources.local.json private/health-checks/RUN_UTC/report.json' < scripts/list-delta.py
```

## Import or fill datasources on a slot

When you prepare common customer links in a batch, read `commonDefaults` from `datasource-fixtures/catalog.json` on Mini. Choose MotherData datasource ids that have already passed a live probe. To add one to a named CloudCanal slot, take the current connection config from MotherData by that id. For a manual instance, take the config from the Lab private ledger by `labRecord`.

Check the type, the target database, the access endpoint, and the Worker. After you are authorized, create or reuse the Console registration. Run the Worker connection test. Record the real CloudCanal datasource id.

The isolated `mysql-pair` case names its source and target with stable keys in `datasource-fixtures/catalog.json`. Read `cloudcanal-service/private/slot-01/source-plan.json` or `slot-02/source-plan.json` for the target slot. Check the branch, the database suffix, the access port, and the Worker. Preview the plan on Air or Pro first.

```sh
ssh -o BatchMode=yes mini 'cat ~/datasource-lab/datasource-fixtures/seed-run.py' | python3 - --slot 01
```

When `mysql-pair` is already authorized to apply, use the same command and add `--cookie-file "$SESSION_FILE"` to Python. Save a private session for that same slot with `login --save-cookie` from [Console automation](../cloudcanal-console-automation/SKILL.md). The importer creates or reuses a registration by the stable `instanceId`. Before reuse, check that the default database saved on the slot matches the plan. Stop on a uniqueness conflict or a config conflict.

By default, test the connection through that slot's Console API with the Worker cluster. Record the real CloudCanal datasource id. A JAR publish reuses the slot metadata database and the registrations already there. For a branch deploy and for API acceptance, use [CloudCanal development and live acceptance](../cloudcanal-dev-test/SKILL.md).

## Disk, images, and cleanup

```sh
ssh -o BatchMode=yes mini '/usr/bin/python3 ~/datasource-lab/disk-status.py --weekly'
```

On every check, record space used by the macOS data disk, the Colima data disk, containers, volumes, images, and slot schemas. Compare those figures with the previous archive. Also check direct health for each running registered slot, for shared Prometheus, and for MotherData.

Inspect a finished `cc-run-*` environment when its owner is clear. Look for an orphan datasource or an exited container it left behind. Check active jobs, CloudCanal registrations, and Docker references.

In the report, list container ids, volumes you can release on their own, image ids and tags, and the estimated space freed. When no container references an image, also check whether a build, a release, or a rollback still needs it.

Run only the report items and the exact ids the user has confirmed. Before you run an item, check its owner, state, and references again. After you run it, record the change you actually saw.

The skill repo holds the programs and the operating rules. On the controlled machine, keep Mini `private/`, real directory snapshots, endpoints, credentials, sessions, release packages, and run reports.
