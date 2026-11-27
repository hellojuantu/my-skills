# Environment and Row V1/V2 Decoder Test

## Contents

1. [Scope and safety](#scope-and-safety)
2. [Reuse a native TiDB](#reuse-a-native-tidb)
3. [Quick TiDB with TiUP](#quick-tidb-with-tiup)
4. [Quick TiDB with official Docker images](#quick-tidb-with-official-docker-images)
5. [Layer B environment](#layer-b-environment)
6. [Decoder matrix](#decoder-matrix)
7. [Run Layer A](#run-layer-a)
8. [Run Layer B](#run-layer-b)
9. [JSON, temporal, and charset expectations](#json-temporal-and-charset-expectations)
10. [Failure classification](#failure-classification)
11. [Known boundaries](#known-boundaries)

## Scope and safety

Layer B directly starts `TiDBInstanceNew` and reads the CloudCanal event store. It verifies the real SQL/PD/TiKV path
but does not run a destination writer and does not cover region/DDL/GC fault cases.

Use an exclusive database such as `cc_tidb_decoder_<run-id>`. The test drops and recreates:

- `cc_row_decoder_it`
- `cc_row_decoder_common_handle_it`
- `cc_row_decoder_charset_it`

The test runner must be able to write and remove its task directory under `$HOME/cloudcanal/data/tidb`. If the JVM is
killed before `finally`, inspect and remove only this run's tables and task data.

## Reuse a native TiDB

Docker is not required. The earlier real run used a TiDB cluster installed directly on a remote Linux host, with SQL at
`192.168.0.180:4000` and PD at `192.168.0.180:2379`. Treat these as historical endpoints, not permanent defaults: check
reachability and confirm that PD belongs to the SQL cluster before using them.

```bash
nc -vz 192.168.0.180 4000
nc -vz 192.168.0.180 2379
curl --fail --silent --show-error http://192.168.0.180:2379/pd/api/v1/status
curl --fail --silent --show-error http://192.168.0.180:2379/pd/api/v1/stores | \
  jq -r '.stores[].store.address'
```

Verify every returned TiKV address from the machine running Gradle. Then set the same Layer B variables used for any
other deployment:

```bash
export CC_TIDB_IT_ENABLED=true
export CC_TIDB_IT_HOST=192.168.0.180:4000
export CC_TIDB_IT_PD=192.168.0.180:2379
export CC_TIDB_IT_USER='<sql-user>'
export CC_TIDB_IT_DATABASE='cc_tidb_decoder_native'
export CC_TIDB_IT_TIMEOUT_SECONDS=180
export CC_TIDB_IT_RANDOM_PAIRS=256
export CC_TIDB_IT_RANDOM_SEED=20260714
# Export CC_TIDB_IT_PASSWORD in the shell; never put it in this repository.
```

SSH access is useful for server logs but is not part of `TestTiInstance`; the test connects directly to SQL, PD, and
TiKV. An unreachable historical host is an environment failure, not a decoder failure.

## Quick TiDB with TiUP

### Install

```bash
curl --proto '=https' --tlsv1.2 -sSf https://tiup-mirrors.pingcap.com/install.sh | sh
source ~/.bash_profile
tiup --version
```

Use v7.5.7 to match the current TiFlow/TiDB 7.5 reference unless the test explicitly targets another version:

```bash
tiup playground v7.5.7 \
  --tag cc-tidb-decoder-it \
  --db 1 \
  --pd 1 \
  --kv 1 \
  --tiflash 0 \
  --without-monitor
```

Keep the foreground terminal running. Read the actual SQL and PD ports from its output; occupied default ports may be
changed.

```bash
mysql -h 127.0.0.1 -P 4000 -u root \
  -e 'SELECT VERSION(), @@SESSION.tidb_row_format_version; CREATE DATABASE IF NOT EXISTS cc_tidb_decoder_local;'

curl --fail --silent --show-error http://127.0.0.1:2379/pd/api/v1/status
```

Playground listens on loopback by default. Add `--host 0.0.0.0` only on an isolated network when a remote worker must
connect, and firewall every SQL/PD/TiKV port. Never expose a root/no-password cluster publicly.

Stop with `Ctrl+C`, then inspect and clean the exact instance:

```bash
tiup status
tiup clean <Name-from-tiup-status>
```

Never use `tiup clean --all` on a shared machine.

Official references:

- [TiDB v7.5 Quick Start](https://docs.pingcap.com/tidb/v7.5/quick-start-with-tidb/)
- [TiUP Playground](https://docs.pingcap.com/tidb/v7.5/tiup-playground/)
- [TiUP clean](https://docs.pingcap.com/tidb/dev/tiup-command-clean/)
- [`tidb_row_format_version`](https://docs.pingcap.com/tidb/stable/system-variables#tidb_row_format_version)

## Quick TiDB with official Docker images

Use this fallback when TiUP is unavailable. These are real PD, TiKV, and TiDB v7.5.7 processes, not mocks. The commands
below match the verified Docker Desktop layout and publish SQL on `14000`, PD on `12379`, and TiKV gRPC on `20160`.

First select a real LAN address of the host. On macOS this is commonly:

```bash
export HOST_LAN_IP="$(ipconfig getifaddr en0)"
test -n "$HOST_LAN_IP"
echo "$HOST_LAN_IP"
```

If `en0` is not the active interface, obtain the address from `ifconfig` or system network settings. Use the same
address in every advertise option. Do not use `host.docker.internal`: containers may resolve it, but the host JVM may
not, and the TiKV Java client follows PD's advertised addresses.

Start a clean, named one-PD/one-TiKV/one-TiDB cluster:

```bash
docker rm -f cc-tidb-it-tidb cc-tidb-it-tikv cc-tidb-it-pd 2>/dev/null || true
docker network inspect cc-tidb-it >/dev/null 2>&1 || docker network create cc-tidb-it

docker run -d --name cc-tidb-it-pd --platform linux/amd64 \
  --network cc-tidb-it -p 12379:2379 -p 12380:2380 \
  pingcap/pd:v7.5.7 \
  --name=cc-pd \
  --data-dir=/data/pd \
  --client-urls=http://0.0.0.0:2379 \
  --advertise-client-urls="http://${HOST_LAN_IP}:12379" \
  --peer-urls=http://0.0.0.0:2380 \
  --advertise-peer-urls=http://cc-tidb-it-pd:2380 \
  --initial-cluster=cc-pd=http://cc-tidb-it-pd:2380

docker run -d --name cc-tidb-it-tikv --platform linux/amd64 \
  --network cc-tidb-it -p 20160:20160 -p 20180:20180 \
  pingcap/tikv:v7.5.7 \
  --addr=0.0.0.0:20160 \
  --advertise-addr="${HOST_LAN_IP}:20160" \
  --status-addr=0.0.0.0:20180 \
  --advertise-status-addr="${HOST_LAN_IP}:20180" \
  --pd="${HOST_LAN_IP}:12379" \
  --data-dir=/data/tikv

docker run -d --name cc-tidb-it-tidb --platform linux/amd64 \
  --network cc-tidb-it -p 14000:4000 -p 11080:10080 \
  pingcap/tidb:v7.5.7 \
  --store=tikv \
  --path="${HOST_LAN_IP}:12379" \
  --host=0.0.0.0 \
  --advertise-address="$HOST_LAN_IP" \
  -P=4000 \
  --status=10080
```

Wait for all three services and verify the advertised TiKV address is `HOST_LAN_IP:20160`, not a container-only
hostname:

```bash
curl --retry 30 --retry-delay 2 --retry-connrefused --fail \
  "http://${HOST_LAN_IP}:12379/pd/api/v1/status"
curl --fail "http://${HOST_LAN_IP}:12379/pd/api/v1/stores" | \
  jq -r '.stores[] | [.store.state_name, .store.address] | @tsv'
curl --retry 30 --retry-delay 2 --retry-connrefused --fail \
  "http://${HOST_LAN_IP}:11080/status"
nc -vz "$HOST_LAN_IP" 20160

mysql -h "$HOST_LAN_IP" -P 14000 -u root \
  -e 'CREATE DATABASE IF NOT EXISTS cc_tidb_decoder_local CHARACTER SET utf8mb4; SELECT VERSION(), @@SESSION.tidb_row_format_version;'
```

Use UTF-8/utf8mb4 by default. `TestTiInstance` uses JDBC `characterEncoding=UTF-8`, and its source config uses
`connectionCharset=utf8`. The focused GBK/latin1 table is created internally only to check decoder compatibility; it
does not require changing the connection default.

Export the Docker endpoints:

```bash
export CC_TIDB_IT_ENABLED=true
export CC_TIDB_IT_HOST="${HOST_LAN_IP}:14000"
export CC_TIDB_IT_PD="${HOST_LAN_IP}:12379"
export CC_TIDB_IT_USER=root
export CC_TIDB_IT_PASSWORD=''
export CC_TIDB_IT_DATABASE=cc_tidb_decoder_local
export CC_TIDB_IT_TIMEOUT_SECONDS=180
export CC_TIDB_IT_RANDOM_PAIRS=256
export CC_TIDB_IT_RANDOM_SEED=20260714
```

After evidence is collected, remove only this named disposable cluster:

```bash
docker rm -f cc-tidb-it-tidb cc-tidb-it-tikv cc-tidb-it-pd
docker network rm cc-tidb-it
```

## Layer B environment

Export all settings as environment variables. This repository does not forward Gradle CLI `-DCC_TIDB_IT_*` values to the
test JVM.

| Variable                     | Required | Meaning                                        |
|------------------------------|----------|------------------------------------------------|
| `CC_TIDB_IT_ENABLED=true`    | yes      | Otherwise both real tests are skipped          |
| `CC_TIDB_IT_HOST`            | yes      | TiDB SQL `host:port`                           |
| `CC_TIDB_IT_PD`              | yes      | PD `host:port`, without `http://`              |
| `CC_TIDB_IT_USER`            | no       | Defaults to `root`                             |
| `CC_TIDB_IT_PASSWORD`        | no       | Defaults to empty; inject securely             |
| `CC_TIDB_IT_DATABASE`        | yes      | Existing, dedicated database                   |
| `CC_TIDB_IT_TIMEOUT_SECONDS` | no       | Per-wait timeout, default 120 seconds          |
| `CC_TIDB_IT_RANDOM_PAIRS`    | no       | Deterministic V1/V2 fixture pairs, default 256 |
| `CC_TIDB_IT_RANDOM_SEED`     | no       | Reproduction seed, default 20260714            |

Although `CC_TIDB_IT_TIMEOUT_SECONDS` is configurable, the real lifecycle method has an outer JUnit timeout of 900
seconds.

The SQL user needs CREATE/DROP/SELECT/INSERT/UPDATE/DELETE and metadata access used by TiDB catalog loading. SQL and PD
must belong to the same cluster.

## Decoder matrix

The primary real table has exactly 78 columns (`id`, `marker`, and 76 payload columns) and covers the 23 tikv-client
3.3.5 `MySQLType` values that can be created as TiDB physical columns:

- signed and unsigned integers, including maximum `BIGINT UNSIGNED`;
- FLOAT and DOUBLE across zero, signed zero, precision thresholds, near-minimum/near-maximum exponents, and random
  exponents;
- DECIMAL across zero, minimum unit, values below one, trailing zeros, rounding, signed/unsigned maxima, precision 65,
  scale 0/6/12/30, and random values;
- BIT(1/8/9/16/32/64);
- CHAR, VARCHAR, BINARY, VARBINARY, all TEXT/BLOB sizes, NULL, and a 70 KB value;
- DATE, DATETIME, TIMESTAMP, TIME, YEAR with FSP 0/3/6, negative TIME, early dates, and zero temporal values;
- ENUM and SET;
- JSON object, array, string, number, uint64, boolean, JSON null, SQL NULL, and TiDB opaque temporal values;
- clustered integer handle and a VARCHAR/INT/DECIMAL/DATE composite common handle.

The focused eight-column charset table adds a clustered GBK key plus GBK and latin1 CHAR/VARCHAR/TEXT columns. It checks
Row V1 and Row V2 INSERT, ordinary UPDATE, and DELETE before-images. The normal connection remains UTF-8.

Representative numeric input-to-CDC assertions are:

| SQL input and column         | Expected CDC value                 |
|------------------------------|------------------------------------|
| `-0.0` in FLOAT/DOUBLE       | `0.0`                              |
| `16777217` in FLOAT          | `1.6777216E7`                      |
| `9007199254740993` in DOUBLE | `9.007199254740992E15`             |
| `123.45` in DECIMAL(20,6)    | `123.450000`                       |
| `1.2300E4` in DECIMAL(20,6)  | `12300.000000`                     |
| `1.2345675` in DECIMAL(20,6) | `1.234568`                         |
| `1.5` in DECIMAL(65,0)       | `2`                                |
| `1E-30` in DECIMAL(65,30)    | `0.000000000000000000000000000001` |

The fixed palette also includes signed/unsigned maxima, minimum subnormal and maximum finite FLOAT/DOUBLE values,
negative counterparts, 65-digit integers, and DECIMAL scale-30 maxima. Values after the palette use deterministic random
exponents and decimal digits.

The lifecycle covers Row V1 and Row V2 INSERT, ordinary UPDATE, DELETE before-columns, common-handle
INSERT/UPDATE/DELETE, charset-table INSERT/UPDATE/DELETE, transaction-end checkpoint, writes while stopped, and
checkpoint restart. Restart asserts at-least-once delivery without loss; it does not promise no duplicate replay.

Keep the fixed golden rows: they cover uint64/BIT64 boundaries, DECIMAL precision 65 with scale 0/30, zero temporal
values, enum/set limits, 70 KB LOBs, opaque JSON, SQL NULL, and common handles. In addition, the real test generates 256
deterministic logical fixtures by default. Each fixture is written once as Row V1 and once as Row V2, then receives an
ordinary UPDATE and DELETE. That is 512 rows and 1,536 randomized CDC row events across the same 78-column schema.
Random LOBs remain small; the fixed golden rows retain large-value boundaries.

The seed and fixture index must appear in a random failure. V1 and V2 use separate sessions with their own
`tidb_row_format_version`; never rewrite both sides through one session. Do not replace the fixed corpus with
random-only coverage.

Two additional unit tests classify every tikv-client `MySQLType`: `TypeNull` and `TypeVarString` are exercised without
physical columns; legacy `TypeDecimal`, `TypeNewDate`, and `TypeGeometry` are explicitly unsupported. Therefore say “all
currently mapped physical types,” not “every possible TiDB type.”

## Run Layer A

```bash
unset CC_TIDB_IT_ENABLED
./gradlew :ds-tidb:cleanTest :ds-tidb:test --no-build-cache
```

Require Gradle success and no failures/errors. Exactly these real environment entries may be skipped:

- `TiDBDsFactoryTest.shouldCreateConfiguredTiDBDataSource`
- `TestTiInstance.shouldDecodeAllPhysicalTypesIdenticallyFromRealRowV1AndV2Cdc`

Record them as not executed. The default run must not connect to a historical office/public TiDB, fixed PD, or real
sorter directory.

`skipped=2` means the offline tests passed but the two real entry points did not execute. It is valid Layer A evidence,
never Layer B PASS. Any other skipped count must be investigated.

## Run Layer B

### Preflight

```bash
git status --short
git diff --check

SQL_HOST="${CC_TIDB_IT_HOST%:*}"
SQL_PORT="${CC_TIDB_IT_HOST##*:}"

mysql -h "$SQL_HOST" -P "$SQL_PORT" -u "${CC_TIDB_IT_USER:-root}" -p \
  -e "CREATE DATABASE IF NOT EXISTS \`${CC_TIDB_IT_DATABASE}\`; SELECT VERSION(), @@SESSION.tidb_row_format_version;"

curl --fail --silent --show-error "http://${CC_TIDB_IT_PD}/pd/api/v1/status"
curl --fail --silent --show-error "http://${CC_TIDB_IT_PD}/pd/api/v1/stores" | \
  jq -r '.stores[].store.address'
```

From the test runner, verify every printed TiKV advertised address is reachable. SQL+PD reachability alone is
insufficient because the CDC client connects directly to TiKV gRPC.

### Full module acceptance

```bash
export CC_TIDB_IT_ENABLED=true
export CC_TIDB_IT_HOST='<tidb-sql-host>:<port>'
export CC_TIDB_IT_PD='<pd-host>:<port>'
export CC_TIDB_IT_USER='<user>'
export CC_TIDB_IT_DATABASE='<dedicated-existing-database>'
export CC_TIDB_IT_TIMEOUT_SECONDS=120
export CC_TIDB_IT_RANDOM_PAIRS=256
export CC_TIDB_IT_RANDOM_SEED=20260714
# Inject CC_TIDB_IT_PASSWORD securely; omit it only for an empty-password test cluster.

./gradlew :ds-tidb:cleanTest :ds-tidb:test --no-build-cache

python3 \
  "$HOME/.codex/skills/cloudcanal-dev-test/skills/tidb/cdc-integration/scripts/verify_junit_results.py" \
  ds-plugins/ds-tidb/build/test-results/test

export CC_COVERAGE_BASE='<merge-base-or-HEAD-for-local-uncommitted-diff>'
python3 \
  "$HOME/.codex/skills/cloudcanal-dev-test/skills/tidb/cdc-integration/scripts/verify_changed_coverage.py" \
  --report ds-plugins/ds-tidb/build/reports/jacoco/test/jacocoTestReport.xml \
  --source-root ds-plugins/ds-tidb/src/main/java \
  --base "$CC_COVERAGE_BASE"
```

Require `:ds-tidb:test` to execute rather than report `UP-TO-DATE` or `FROM-CACHE`. The verifier requires aggregate
failures/errors/skips to be zero and checks that both real entry points executed.

The bundled changed-line verifier reads JaCoCo XML and requires every executable Java line added or changed relative
to `CC_COVERAGE_BASE` to execute. Use `HEAD` for local staged/unstaged work and the PR merge base in CI. Branch coverage
is printed as additional information but is not substituted for the 100% changed-line gate.

For diagnosis only, run the two involved classes. Require the datasource test and the real lifecycle method to be
present and unskipped; do not hardcode an aggregate count because `TestTiInstance` also contains offline type,
random-generator, and charset guards:

```bash
./gradlew :ds-tidb:cleanTest :ds-tidb:test --no-build-cache \
  --tests 'com.clougence.cloudcanal.tidb.TiDBDsFactoryTest' \
  --tests 'com.clougence.cloudcanal.tidb.worker.reader.incre_new.TestTiInstance'
```

Do not use the filtered run as final Layer B acceptance.

## JSON, temporal, and charset expectations

TiDB BinaryJSON canonicalizes object key order and discards source-text whitespace. Writing:

```json
{"stage": "insert", "max": 18446744073709551615}
```

must decode as:

```json
{"max": 18446744073709551615, "stage": "insert"}
```

Require one space after commas and colons, no leading/trailing whitespace, no newline, canonical TiDB key order, and
lossless uint64.

The decoder preserves zero temporal values as strings such as `0000-00-00` and `0000-00-00 00:00:00.000000`. Converting
them to target NULL is a downstream writer policy, not a decoder expectation.

For ordinary text, compare Java strings as Unicode and use UTF-8 by default. For the focused charset table, also compare
SQL `HEX(...)` so a visually correct string cannot hide byte corruption. TiDB v7.5 Row V2 restored data is required for
non-binary string columns such as the GBK common handle. The golden assertions intentionally differ:

- GBK columns use GBK source bytes, for example `中文GBK` is `D6D0CEC447424B`.
- In this TiDB v7.5 compatibility path, the tested latin1 values remain UTF-8 row bytes, for example `Café` is
  `436166C3A9` rather than `436166E9`.

Do not generalize this narrow golden into a request to change CloudCanal's default charset. Keep the application
connection UTF-8 and use SQL `HEX` only when diagnosing non-UTF-8 storage.

## Failure classification

| Symptom                                | Check first                                 | Do not                                  |
|----------------------------------------|---------------------------------------------|-----------------------------------------|
| JDBC timeout/refused                   | SQL address, network, database, grants      | Modify decoder                          |
| `Failed to init client for PD cluster` | Same-cluster PD and network                 | Swap in an unrelated PD                 |
| Subscribe timeout                      | filter, catalog, grants, initialization log | Increase timeout indefinitely           |
| Marker/checkpoint timeout              | async failure, resolvedTs, event store      | Ignore the first failure and rerun only |
| JSON/type mismatch                     | actual value, column, V1/V2, TiDB version   | Change expected only to make green      |
| Cleanup failure                        | exact table and run task directory          | Delete ranges from unknown RocksDB data |
| Gradle success with skipped test       | environment switch and JUnit XML            | Report PASS                             |

## Known boundaries

List these as untested unless separate evidence exists:

- legacy common-handle collation with `new_collation_enabled=false`;
- `utf8mb4_0900_*` common handles, whose collation ids are not preserved by tikv-client 3.3.5;
- old rows after `ALTER ADD COLUMN` requiring origin default/zero value;
- virtual versus stored generated columns;
- TiDB 8.5 `VECTOR FLOAT32`;
- key-only delete for prefix or restored-data common handles; the real lifecycle uses old values;
- exactly-once restart delivery; the checkpoint case proves no loss but allows replay.
