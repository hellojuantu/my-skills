#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time

try:
    import pymysql
except ImportError:
    print("pymysql is required: python3 -m pip install pymysql", file=sys.stderr)
    raise


DEFAULT_TABLES = [
    "cc_cdc_dml_main",
    "cc_cdc_region_01",
    "cc_cdc_region_02",
    "cc_cdc_region_03",
    "cc_cdc_txn_conflict",
    "cc_cdc_partition_main",
    "cc_CDC_MixedCase",
]


def env(name, default=None):
    return os.environ.get(name, default)


def add_common_args(parser):
    parser.add_argument("--src-host", default=env("CC_SRC_HOST", "127.0.0.1"))
    parser.add_argument("--src-port", type=int, default=int(env("CC_SRC_PORT", "4000")))
    parser.add_argument("--src-user", default=env("CC_SRC_USER", "root"))
    parser.add_argument("--src-pass", default=env("CC_SRC_PASS", ""))
    parser.add_argument("--dst-host", default=env("CC_DST_HOST", "127.0.0.1"))
    parser.add_argument("--dst-port", type=int, default=int(env("CC_DST_PORT", "3306")))
    parser.add_argument("--dst-user", default=env("CC_DST_USER", "root"))
    parser.add_argument("--dst-pass", default=env("CC_DST_PASS", ""))
    parser.add_argument("--db", default=env("CC_TEST_DB", "cc_tidb_cdc_test"))
    parser.add_argument("--timeout", type=int, default=180)


def connect(args, side, database=None):
    if side == "src":
        host, port, user, password = args.src_host, args.src_port, args.src_user, args.src_pass
    else:
        host, port, user, password = args.dst_host, args.dst_port, args.dst_user, args.dst_pass
    params = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "autocommit": True,
        "charset": "utf8mb4",
    }
    if database:
        params["database"] = database
    return pymysql.connect(**params)


def selected_db(args, database):
    return args.db if database is None else database


def fetch_one(args, side, sql, params=None, database=None):
    with connect(args, side, selected_db(args, database)) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()[0]


def fetch_all(args, side, sql, params=None, database=None):
    with connect(args, side, selected_db(args, database)) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()


def exec_sql(args, side, sql, params=None, database=None):
    with connect(args, side, selected_db(args, database)) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            try:
                rows = cur.fetchall()
                if rows:
                    print("SQL_RESULT", rows)
            except Exception:
                pass


def exec_many(args, side, sql, values, database=None):
    with connect(args, side, selected_db(args, database)) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, values)


def prepare_schema(args):
    db = args.db
    exec_sql(args, "src", f"CREATE DATABASE IF NOT EXISTS `{db}`", database="")
    dml = f"""
CREATE TABLE IF NOT EXISTS `{db}`.`cc_cdc_dml_main` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `email` VARCHAR(128) NOT NULL,
  `age` INT DEFAULT NULL,
  `salary` DECIMAL(12, 2) DEFAULT NULL,
  `is_active` TINYINT DEFAULT 1,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `birthday` DATE DEFAULT NULL,
  `login_time` DATETIME DEFAULT NULL,
  `profile` VARCHAR(255) DEFAULT NULL,
  `score` DOUBLE DEFAULT NULL,
  `balance` DOUBLE DEFAULT NULL,
  `data_json` JSON DEFAULT NULL,
  `binary_data` VARBINARY(64) DEFAULT NULL,
  UNIQUE KEY `uk_cc_cdc_dml_username` (`username`),
  KEY `idx_cc_cdc_dml_email` (`email`)
)
"""
    exec_sql(args, "src", dml)
    for table in ["cc_cdc_region_01", "cc_cdc_region_02", "cc_cdc_region_03"]:
        exec_sql(args, "src", f"CREATE TABLE IF NOT EXISTS `{db}`.`{table}` LIKE `{db}`.`cc_cdc_dml_main`")
    exec_sql(
        args,
        "src",
        f"""
CREATE TABLE IF NOT EXISTS `{db}`.`cc_cdc_txn_conflict` (
  `id` BIGINT PRIMARY KEY,
  `uid` BIGINT DEFAULT NULL,
  `count_value` INT DEFAULT 0,
  `remark` VARCHAR(128) DEFAULT NULL,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
""",
    )
    exec_sql(
        args,
        "src",
        f"""
CREATE TABLE IF NOT EXISTS `{db}`.`cc_cdc_partition_main` (
  `id` BIGINT NOT NULL,
  `username` VARCHAR(64) NOT NULL,
  `email` VARCHAR(128) DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
)
PARTITION BY RANGE COLUMNS (`id`) (
  PARTITION p0 VALUES LESS THAN (1000),
  PARTITION p1 VALUES LESS THAN (2000),
  PARTITION p2 VALUES LESS THAN (3000),
  PARTITION p3 VALUES LESS THAN (4000)
)
""",
    )
    exec_sql(
        args,
        "src",
        f"""
CREATE TABLE IF NOT EXISTS `{db}`.`cc_CDC_MixedCase` (
  `ID` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `UserName` VARCHAR(64) NOT NULL,
  `Email` VARCHAR(128) DEFAULT NULL,
  `Extra_Col` VARCHAR(64) DEFAULT NULL,
  UNIQUE KEY `uk_cc_cdc_mixed_username` (`UserName`)
)
""",
    )
    print(f"prepared source schema {db}")


def counts(args):
    print("TABLE_COUNTS")
    ok = True
    for table in args.tables:
        src = fetch_one(args, "src", f"SELECT COUNT(*) FROM `{table}`")
        dst = fetch_one(args, "dst", f"SELECT COUNT(*) FROM `{table}`")
        same = src == dst
        ok = ok and same
        print(table, src, dst, "OK" if same else "DIFF")
    return 0 if ok else 1


def marker_counts(args):
    where = args.where or f"{args.column} LIKE %s"
    params = None if args.where else (args.marker + "%",)
    src = fetch_one(args, "src", f"SELECT COUNT(*) FROM `{args.table}` WHERE {where}", params)
    dst = fetch_one(args, "dst", f"SELECT COUNT(*) FROM `{args.table}` WHERE {where}", params)
    print("MARKER", args.table, args.marker, src, dst, "OK" if src == dst else "DIFF")
    return 0 if src == dst else 1


def wait_until(label, timeout, fn):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = fn()
        if last:
            print(label, "OK", last)
            return last
        time.sleep(2)
    raise RuntimeError(f"{label} timeout, last={last!r}")


def post_probe(args):
    marker = args.marker or "codex_post_probe_" + time.strftime("%Y%m%d%H%M%S")
    table = args.table
    base = fetch_one(args, "src", f"SELECT COALESCE(MAX(id), {args.id_base}) + 1 FROM `{table}` WHERE id BETWEEN {args.id_base} AND 999999")
    if base < args.id_base:
        base = args.id_base
    exec_sql(
        args,
        "src",
        f"INSERT INTO `{table}` (`id`, `username`, `email`, `age`, `profile`) VALUES (%s,%s,%s,42,%s)",
        (base, marker, marker + "@test.com", "post_probe"),
    )
    print("inserted", table, marker, base)
    wait_until(
        "post_probe",
        args.timeout,
        lambda: fetch_one(args, "dst", f"SELECT COUNT(*) FROM `{table}` WHERE `username`=%s", (marker,)) == 1,
    )


def tiup_pd(args, action):
    if not args.pd_url or not args.evict_store_id:
        return
    scheduler = f"evict-leader-scheduler-{args.evict_store_id}"
    if action == "add":
        cmd = ["tiup", "ctl:v8.5.4", "pd", "-u", args.pd_url, "scheduler", "add", "evict-leader-scheduler", str(args.evict_store_id)]
    else:
        cmd = ["tiup", "ctl:v8.5.4", "pd", "-u", args.pd_url, "scheduler", "remove", scheduler]
    print("RUN", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=False)


def combo_stress(args):
    if not args.allow_truncate:
        raise SystemExit("combo-stress requires --allow-truncate because it truncates cc_cdc_region_03")
    marker = args.marker or "codex_mix_" + time.strftime("%Y%m%d%H%M%S")
    print("MARKER=" + marker, flush=True)
    tiup_pd(args, "add")
    try:
        region_base = fetch_one(args, "src", "SELECT COALESCE(MAX(id), 900000) + 1 FROM `cc_cdc_region_01` WHERE id BETWEEN 900000 AND 999000")
        if region_base < 900000:
            region_base = 900000
        if region_base + 20 >= 999000:
            raise RuntimeError(f"region_01 id range exhausted: {region_base}")
        before = [(region_base + i, f"{marker}_r1_before_{i}", f"{marker}_r1_before_{i}@test.com", 20 + i, "before_split") for i in range(1, 11)]
        exec_many(args, "src", "INSERT INTO `cc_cdc_region_01` (`id`,`username`,`email`,`age`,`profile`) VALUES (%s,%s,%s,%s,%s)", before)
        print("inserted region_01 before split: 10", flush=True)
        exec_sql(args, "src", "SPLIT TABLE `cc_cdc_region_01` BETWEEN (0) AND (1000000) REGIONS 16")
        print("split region_01 done", flush=True)
        after = [(region_base + i, f"{marker}_r1_after_{i}", f"{marker}_r1_after_{i}@test.com", 20 + i, "after_split") for i in range(11, 21)]
        exec_many(args, "src", "INSERT INTO `cc_cdc_region_01` (`id`,`username`,`email`,`age`,`profile`) VALUES (%s,%s,%s,%s,%s)", after)
        print("inserted region_01 after split: 10", flush=True)

        exec_sql(args, "src", "TRUNCATE TABLE `cc_cdc_region_03`")
        trunc_rows = [(i, f"{marker}_trunc_{i}", f"{marker}_trunc_{i}@test.com", 30 + i, "after_truncate") for i in range(1, 6)]
        exec_many(args, "src", "INSERT INTO `cc_cdc_region_03` (`id`,`username`,`email`,`age`,`profile`) VALUES (%s,%s,%s,%s,%s)", trunc_rows)
        print("truncated region_03 and inserted 5", flush=True)

        parts = [r[0] for r in fetch_all(args, "src", "SELECT partition_name FROM information_schema.partitions WHERE table_schema=%s AND table_name='cc_cdc_partition_main' AND partition_name IS NOT NULL", (args.db,), database="information_schema")]
        if "p4" not in parts:
            exec_sql(args, "src", "ALTER TABLE `cc_cdc_partition_main` ADD PARTITION (PARTITION p4 VALUES LESS THAN (5000))")
            print("added partition p4", flush=True)
        p4_base = fetch_one(args, "src", "SELECT COALESCE(MAX(id), 4100) + 1 FROM `cc_cdc_partition_main` WHERE id >= 4000 AND id < 4990")
        if p4_base < 4101:
            p4_base = 4101
        if p4_base + 3 >= 5000:
            raise RuntimeError(f"p4 id range exhausted: {p4_base}")
        p4_rows = [(p4_base + i, f"{marker}_p4_{i}", f"{marker}_p4_{i}@test.com") for i in range(1, 4)]
        exec_many(args, "src", "INSERT INTO `cc_cdc_partition_main` (`id`,`username`,`email`) VALUES (%s,%s,%s)", p4_rows)
        print("inserted partition p4: 3", flush=True)
    finally:
        if args.evict_store_id:
            time.sleep(args.evict_seconds)
            tiup_pd(args, "remove")

    def done():
        c = {
            "src_r1": fetch_one(args, "src", "SELECT COUNT(*) FROM `cc_cdc_region_01` WHERE `username` LIKE %s", (marker + "_r1_%",)),
            "dst_r1": fetch_one(args, "dst", "SELECT COUNT(*) FROM `cc_cdc_region_01` WHERE `username` LIKE %s", (marker + "_r1_%",)),
            "src_r3_total": fetch_one(args, "src", "SELECT COUNT(*) FROM `cc_cdc_region_03`"),
            "dst_r3_total": fetch_one(args, "dst", "SELECT COUNT(*) FROM `cc_cdc_region_03`"),
            "src_r3_marker": fetch_one(args, "src", "SELECT COUNT(*) FROM `cc_cdc_region_03` WHERE `username` LIKE %s", (marker + "_trunc_%",)),
            "dst_r3_marker": fetch_one(args, "dst", "SELECT COUNT(*) FROM `cc_cdc_region_03` WHERE `username` LIKE %s", (marker + "_trunc_%",)),
            "src_p4": fetch_one(args, "src", "SELECT COUNT(*) FROM `cc_cdc_partition_main` WHERE `username` LIKE %s", (marker + "_p4_%",)),
            "dst_p4": fetch_one(args, "dst", "SELECT COUNT(*) FROM `cc_cdc_partition_main` WHERE `username` LIKE %s", (marker + "_p4_%",)),
        }
        print("COUNTS", c, flush=True)
        if c["src_r1"] == c["dst_r1"] == 20 and c["src_r3_total"] == c["dst_r3_total"] == 5 and c["src_r3_marker"] == c["dst_r3_marker"] == 5 and c["src_p4"] == c["dst_p4"] == 3:
            return c
        return None

    wait_until("combo_stress", args.timeout, done)
    print("RESULT=PASS")


def build_parser():
    parser = argparse.ArgumentParser(description="CloudCanal TiDB CDC database-side test helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare-schema")
    add_common_args(p)
    p.set_defaults(func=prepare_schema)

    p = sub.add_parser("counts")
    add_common_args(p)
    p.add_argument("--tables", nargs="*", default=DEFAULT_TABLES)
    p.set_defaults(func=lambda args: sys.exit(counts(args)))

    p = sub.add_parser("marker-counts")
    add_common_args(p)
    p.add_argument("--table", required=True)
    p.add_argument("--marker", required=True)
    p.add_argument("--column", default="username")
    p.add_argument("--where")
    p.set_defaults(func=lambda args: sys.exit(marker_counts(args)))

    p = sub.add_parser("post-probe")
    add_common_args(p)
    p.add_argument("--table", default="cc_cdc_region_02")
    p.add_argument("--marker")
    p.add_argument("--id-base", type=int, default=920000)
    p.set_defaults(func=post_probe)

    p = sub.add_parser("combo-stress")
    add_common_args(p)
    p.add_argument("--pd-url")
    p.add_argument("--evict-store-id", type=int)
    p.add_argument("--evict-seconds", type=int, default=8)
    p.add_argument("--allow-truncate", action="store_true")
    p.add_argument("--marker")
    p.set_defaults(func=combo_stress)
    return parser


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
