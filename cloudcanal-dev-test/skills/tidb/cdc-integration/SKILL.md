---
name: cloudcanal-tidb-cdc-integration-test
description: Run and report CloudCanal TiDB source integration tests, including the ds-tidb baseline, real TiDB datasource connectivity, Row V1/V2 all-physical-type insert/update/delete and checkpoint recovery, and the 18-case source-to-target CDC fault suite. Use when validating TiDB decoder changes, reproducing TiKV CDC failures, preparing a TiDB playground, checking skipped real tests, or producing evidence for a complete TiDB CDC regression.
---

# CloudCanal TiDB CDC Integration Test

Execute only the scope the user requests, but never let a smaller layer stand in for a larger one:

- Layer A: offline `ds-tidb` baseline. Two real-environment tests may be skipped.
- Layer B: full `ds-tidb` module against a real TiDB. Require zero failures, errors, and skips.
- Layer C: actual CloudCanal source-to-target task, 18 independent CDC cases, and combined stress.

Report `BLOCKED`, `NOT RUN`, and `NOT TRIGGERED` honestly. Never convert them to PASS.

## Select and load references

- For native/TiUP/Docker setup, Layer A/B commands, environment variables, decoder coverage, JSON expectations, and
  JUnit verification, read [references/environment-and-decoder.md](references/environment-and-decoder.md) completely.
- Before reviewing or changing type decoding,
  read [references/upstream-type-sources.md](references/upstream-type-sources.md) completely. Use its pinned TiFlow,
  TiDB, and tikv-client paths as the comparison baseline.
- For any CloudCanal end-to-end, fault, DDL, partition, restart, GC, log, metric, or 18-case request,
  read [references/e2e-case-plan.md](references/e2e-case-plan.md) completely.
- For a full suite, read both references before changing the environment.

## Enforce safety gates

1. Read the repository `AGENTS.md` files and inspect `git status --short`.
2. Preserve unrelated user changes.
3. Use a disposable cluster or dedicated source and target databases. Never point target back to source.
4. State every table the run will drop and require exclusive use of the test database.
5. Require explicit `ALLOW_DESTRUCTIVE=true` before split, leader eviction, timeout injection, truncate, partition, GC,
   or combined-stress operations.
6. Keep credentials out of code, commands shown in reports, logs, and commits.
7. Never write to or delete ranges from an unknown CloudCanal sorter/RocksDB directory.

If a gate cannot be satisfied, stop the destructive portion and report the exact blocker. Continue only with safe
read-only or offline checks.

## Run Layer A

Unset the real-test switch and run the complete module without build cache. Confirm Gradle executed the task and inspect
JUnit XML. Treat the two expected real-environment skips as “not executed,” not passed.

Do not use Layer A as evidence for real SQL, PD, TiKV CDC, checkpoint, or target behavior.

## Run Layer B

1. Reuse a reachable dedicated native TiDB when available. Otherwise follow the TiUP or official Docker quick start. Use
   one TiDB, one PD, and one TiKV for decoder work.
2. Verify SQL, PD, and every TiKV advertised gRPC address from the test runner.
3. Create a dedicated database and export every `CC_TIDB_IT_*` variable. Do not use Gradle `-D` properties; this build
   does not forward them to the test JVM.
4. Run the entire `:ds-tidb:test` task with `cleanTest` and `--no-build-cache`, without test filters.
5. Run `scripts/verify_junit_results.py` against the generated result directory.
6. Run the fixed 78-column table, the focused charset table, and the default 256 deterministic random Row V1/V2 fixture
   pairs unless the user explicitly requests a larger count. Preserve the reported seed for reproduction.
7. Run `scripts/verify_changed_coverage.py` against the generated JaCoCo XML with the correct diff base and require
   100% changed executable-line coverage.
8. Require the datasource smoke test and the real Row V1/V2 lifecycle test to exist and execute, and require aggregate
   `failures=0`, `errors=0`, `skipped=0`.

Use filtered test classes only to diagnose a failure. Never report a filtered run as the final Layer B result.

## Run Layer C

1. Use the multi-node topology and prerequisites from the case plan. A single-host playground can validate state
   transitions but not physical host resilience.
2. If the executing Codex environment provides the `cloudcanal-console-automation` skill, load it before creating,
   changing, stopping, restarting, or deleting the CloudCanal task. Otherwise use the deployment's supported console/API
   and record the exact operation; never invent an endpoint or payload.
3. Before creating the CloudCanal task, apply `scripts/tidb-cdc-integration-schema.sql` to the dedicated source
   database. The script drops and recreates seven test tables.
4. Create a new full+increment CloudCanal task to a dedicated target. Enable DDL sync and subscribe all seven tables.
5. Wait for full sync, puller initialization, resolvedTs, and checkpoint progress.
6. Generate a unique UTC run id. Record task id, versions, topology, task parameters, log paths, and log offsets.
7. Execute cases 1 through 18 independently in the documented order. For every case, collect:
    - the exact action and fault window;
    - unique marker values;
    - source and target counts plus critical field values;
    - expected error, reschedule, and re-initialization sequence where applicable;
    - fatal-marker scan after the case offset;
    - a post-case DML probe.
8. Run combined stress only after the independent cases pass. Never use it to replace an independent result.
9. Restore every scheduler, timeout, fast-fail, flush, GC, and parallelism setting in a finally-style cleanup step.

Mark a fault branch PASS only when the expected fault actually appears and recovery plus data consistency are both
proven.

## Report the result

Lead with the highest fully completed layer. Include:

- code revision and dirty-worktree summary;
- CloudCanal and TiDB versions and topology;
- Layer A aggregate counts, including skips;
- Layer B aggregate counts and explicit datasource/Row V1/V2 results;
- randomized pair count, DML count, and seed;
- changed executable-line coverage result and diff base;
- Layer C case-by-case PASS/FAIL/BLOCKED/NOT TRIGGERED status with marker, count, and log evidence;
- combined-stress status;
- final metrics and post-probe result;
- restored parameters and remaining cleanup;
- first failure with the original error;
- known untested boundaries.

Only write “complete integration suite passed” when Layer B has zero skips and all 18 Layer C cases plus combined stress
have direct evidence.
