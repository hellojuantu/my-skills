# Upstream Type-Decoding Baseline

Use this reference only for TiDB row/key type representation. Do not expand a type-decoder change into CDC lifecycle,
retry, DDL, or resource-cleanup changes.

## Pinned versions

| Component            | Baseline                                                        | Purpose                                                                       |
|----------------------|-----------------------------------------------------------------|-------------------------------------------------------------------------------|
| TiFlow               | tag `v7.5.0`, commit `8c006b38bdc304201d646c35c993156abcc2b845` | CDC row decode and final column value representation                          |
| TiDB                 | tag `v7.5.0`, commit `069631e2ecfedc000ffb92c67207bea81380f020` | Row V1/V2 encoding, unflattening, common handles, temporal and JSON semantics |
| TiDB JSON comparison | commit `ec2731b8f53993987b756ecda000789a364c5064`               | BinaryJSON string formatting comparison used by the Java formatter review     |
| tikv-client-java     | Maven `org.tikv:tikv-client-java:3.3.5`                         | The exact Java metadata, codec, and type APIs compiled by `ds-tidb`           |

Compare against the deployed TiDB version too. A newer upstream implementation is guidance, not proof that a behavior is
safe with tikv-client 3.3.5.

## Read these paths first

TiFlow v7.5.0:

- `cdc/entry/codec.go`: `decodeRowV1`, `decodeRowV2`, and `unflatten`.
- `cdc/entry/mounter.go`: `formatColVal` and default/zero-value handling; this is the final CDC-facing type
  representation.
- `tests/integration_tests/row_format/run.sh` and `data/step1.sql` through `step4.sql`: upstream Row V1/V2 integration
  flow.

TiDB v7.5.0:

- `pkg/util/rowcodec/encoder.go` and `decoder.go`: Row V2 byte layout and restored-data decisions.
- `pkg/tablecodec/tablecodec.go`: Row V1/V2 dispatch, `DecodeHandleToDatumMap`, and `Unflatten`.
- `pkg/types/etc.go` and `etc_test.go`: `NeedRestoredData`, including VARCHAR, binary collation, GBK, and
  `utf8mb4_0900_bin` cases.
- `pkg/types/json_binary.go`: BinaryJSON layout and canonical string conversion.
- `pkg/types/time.go` and `pkg/types/core_time.go`: date, datetime, timestamp, zero temporal, and FSP behavior.

tikv-client-java 3.3.5 source JAR:

- `org/tikv/common/codec/TableCodecV1.java`
- `org/tikv/common/codec/TableCodecV2.java`
- `org/tikv/common/codec/RowDecoderV2.java`
- `org/tikv/common/types/DataType.java` and concrete classes such as `IntegerType`, `BitType`, `StringType`, `DateType`,
  `DateTimeType`, and `JsonType`
- `org/tikv/common/meta/Collation.java`

Locate the exact source JAR without downloading an arbitrary branch:

```bash
find "$HOME/.gradle/caches/modules-2/files-2.1/org.tikv/tikv-client-java/3.3.5" \
  -name '*sources.jar' -print
```

## Parity rules

1. Decode Row V1 and Row V2 through their actual layouts, then produce the same logical value for the same SQL column.
2. Match TiFlow's CDC-facing representation, not JDBC display formatting. In particular, preserve unsigned integers,
   fixed-width BIT, temporal FSP and zero values, enum/set values, binary bytes, and canonical BinaryJSON.
3. Decode common-handle key columns with TiDB's restored-data rules. A value present in the row is authoritative when
   the handle alone is lossy.
4. Use UTF-8 for normal CloudCanal string handling. Keep non-UTF-8 checks narrow: compare decoded Unicode plus source
   SQL `HEX(...)` for GBK/latin1 fixtures.
5. Prove every type change with unit tests and the real Row V1/V2 INSERT/UPDATE/DELETE lifecycle. An upstream code
   citation alone is not a pass.

## Collation limitation in tikv-client 3.3.5

The 3.3.5 `Collation` map includes `gbk_bin` and `gbk_chinese_ci`, so the focused GBK common-handle test is meaningful.
It does not include TiDB's newer `utf8mb4_0900_*` collations. Unknown names fall back to code 83 (`utf8_bin`) when
translating name to code, and unknown codes translate to an empty name.

Consequences:

- Do not claim real `utf8mb4_0900_bin` common-handle coverage through tikv-client 3.3.5 metadata.
- Keep explicit Java logic/tests for upstream semantics if needed, but label the live 3.3.5 path limitation.
- Do not add broad charset conversion to compensate. Default application strings remain UTF-8; verify GBK/latin1 only
  with the dedicated golden table and SQL `HEX` evidence.
