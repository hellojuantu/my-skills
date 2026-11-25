import hashlib
import json
import random
from datetime import datetime, timedelta

from cc_console.datasource import choose_test_host, normalize_ds_type

from .base import DatabaseAdapter, AdapterCapabilityError, parse_host_port, require_temp_schema, snapshots_equal


MYSQL_FAMILY = {
    "MySQL",
    "AuroraMySQL",
    "DRDS",
    "GaussDBForMySQL",
    "MariaDB",
    "OceanBase",
    "PolarDbMySQL",
    "PolarDbX",
    "TdsqlCMySQL",
    "TdsqlMySQL",
    "TiDB",
}
MYSQL_PROTOCOL_TARGETS = MYSQL_FAMILY | {"StarRocks", "Doris", "SelectDB"}
DEFAULT_PROFILE = "mysql-core-4"


def quote_ident(name):
    return "`" + str(name).replace("`", "``") + "`"


def qname(schema, table):
    return quote_ident(schema) + "." + quote_ident(table)


class MySqlFamilyAdapter(DatabaseAdapter):
    name = "mysql-family"
    data_source_types = tuple(sorted(MYSQL_PROTOCOL_TARGETS))
    source_data_types = tuple(sorted(MYSQL_FAMILY))
    target_data_types = tuple(sorted(MYSQL_PROTOCOL_TARGETS))
    driver_modules = ("pymysql",)
    install_commands = ("python3 -m pip install pymysql",)
    default_profile = DEFAULT_PROFILE
    data_model = "rdb-mysql-protocol"
    can_init_source = True
    can_prepare_target = True
    can_cleanup = True
    can_faker_crud = True
    can_compare = True

    def _connect(self, ds, password, user=None, db=None, host_type=None, host=None):
        self.require_dependencies()
        import pymysql

        ds_type = normalize_ds_type(ds.get("dataSourceType"))
        default_port = 3306 if ds_type in MYSQL_PROTOCOL_TARGETS else None
        host_value, _resolved_host_type = choose_test_host(ds, host_type, host)
        resolved_host, port = parse_host_port(host_value, default_port)
        account = user or ds.get("accountName")
        if not account:
            raise ValueError("datasource accountName is empty, dataSourceId=" + str(ds.get("id")))
        if password is None:
            raise ValueError("password is required for datasource " + str(ds.get("id")) + " data operations")
        return pymysql.connect(
            host=resolved_host,
            port=port,
            user=account,
            password=password,
            database=db,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=10,
            read_timeout=60,
            write_timeout=60,
        )

    def _table_ddls(self, profile):
        if profile != DEFAULT_PROFILE:
            raise AdapterCapabilityError("unsupported MySQL-family profile: " + profile)
        return [
            (
                "pk_int_table",
                """
                CREATE TABLE {table} (
                  id INT NOT NULL,
                  code VARCHAR(64) NOT NULL,
                  amount DECIMAL(18,2) NULL,
                  payload VARCHAR(255) NULL,
                  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "pk_int_auto_table",
                """
                CREATE TABLE {table} (
                  id INT NOT NULL AUTO_INCREMENT,
                  code VARCHAR(64) NOT NULL,
                  amount DECIMAL(18,2) NULL,
                  payload VARCHAR(255) NULL,
                  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "pk_varchar_table",
                """
                CREATE TABLE {table} (
                  id VARCHAR(64) NOT NULL,
                  code VARCHAR(64) NOT NULL,
                  amount DECIMAL(18,2) NULL,
                  payload VARCHAR(255) NULL,
                  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "pk_timestamp_table",
                """
                CREATE TABLE {table} (
                  id DATETIME NOT NULL,
                  code VARCHAR(64) NOT NULL,
                  amount DECIMAL(18,2) NULL,
                  payload VARCHAR(255) NULL,
                  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
        ]

    def profile_tables(self, profile):
        return [name for name, _ddl in self._table_ddls(profile)]

    def _seed_table(self, cur, schema, table, rows):
        if table == "pk_int_table":
            for i in range(1, rows + 1):
                cur.execute(
                    "INSERT INTO " + qname(schema, table) + " (id, code, amount, payload) VALUES (%s, %s, %s, %s)",
                    (i, "code_" + str(i), i * 1.11, "seed-" + table + "-" + str(i)),
                )
        elif table == "pk_int_auto_table":
            for i in range(1, rows + 1):
                cur.execute(
                    "INSERT INTO " + qname(schema, table) + " (code, amount, payload) VALUES (%s, %s, %s)",
                    ("code_" + str(i), i * 1.11, "seed-" + table + "-" + str(i)),
                )
        elif table == "pk_varchar_table":
            for i in range(1, rows + 1):
                cur.execute(
                    "INSERT INTO " + qname(schema, table) + " (id, code, amount, payload) VALUES (%s, %s, %s, %s)",
                    ("vk_" + str(i), "code_" + str(i), i * 1.11, "seed-" + table + "-" + str(i)),
                )
        elif table == "pk_timestamp_table":
            base = datetime(2026, 1, 1, 0, 0, 0)
            for i in range(1, rows + 1):
                pk_value = (base + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    "INSERT INTO " + qname(schema, table) + " (id, code, amount, payload) VALUES (%s, %s, %s, %s)",
                    (pk_value, "code_" + str(i), i * 1.11, "seed-" + table + "-" + str(i)),
                )

    def init_source_dataset(self, ds, password, schema, rows, profile, drop_existing, allow_non_temp, **kwargs):
        ds_type = normalize_ds_type(ds.get("dataSourceType"))
        if not self.supports_source(ds_type):
            raise AdapterCapabilityError("MySQL-family faker source does not support " + ds_type)
        require_temp_schema(schema, allow_non_temp)
        conn = self._connect(ds, password, user=kwargs.get("user"), host_type=kwargs.get("host_type"), host=kwargs.get("host"))
        try:
            with conn.cursor() as cur:
                if drop_existing:
                    cur.execute("DROP DATABASE IF EXISTS " + quote_ident(schema))
                cur.execute("CREATE DATABASE IF NOT EXISTS " + quote_ident(schema) + " DEFAULT CHARACTER SET utf8mb4")
                for table, ddl in self._table_ddls(profile):
                    cur.execute("DROP TABLE IF EXISTS " + qname(schema, table))
                    cur.execute(ddl.format(table=qname(schema, table)))
                    self._seed_table(cur, schema, table, rows)
        finally:
            conn.close()
        return {"schema": schema, "profile": profile, "tables": self.profile_tables(profile), "seedRowsPerTable": rows}

    def prepare_target_dataset(self, ds, password, schema, drop_existing, allow_non_temp, **kwargs):
        ds_type = normalize_ds_type(ds.get("dataSourceType"))
        if not self.supports_target(ds_type):
            raise AdapterCapabilityError("MySQL-family target prepare does not support " + ds_type)
        require_temp_schema(schema, allow_non_temp)
        conn = self._connect(ds, password, user=kwargs.get("user"), host_type=kwargs.get("host_type"), host=kwargs.get("host"))
        try:
            with conn.cursor() as cur:
                if drop_existing:
                    cur.execute("DROP DATABASE IF EXISTS " + quote_ident(schema))
                cur.execute("CREATE DATABASE IF NOT EXISTS " + quote_ident(schema) + " DEFAULT CHARACTER SET utf8mb4")
        finally:
            conn.close()
        return {"schema": schema}

    def cleanup_dataset(self, ds, password, schema, allow_non_temp, **kwargs):
        require_temp_schema(schema, allow_non_temp)
        conn = self._connect(ds, password, user=kwargs.get("user"), host_type=kwargs.get("host_type"), host=kwargs.get("host"))
        try:
            with conn.cursor() as cur:
                cur.execute("DROP DATABASE IF EXISTS " + quote_ident(schema))
        finally:
            conn.close()
        return {"schema": schema, "dropped": True}

    def faker_crud(self, ds, password, schema, rounds, profile, seed, allow_non_temp, **kwargs):
        ds_type = normalize_ds_type(ds.get("dataSourceType"))
        if not self.supports_source(ds_type):
            raise AdapterCapabilityError("MySQL-family faker CRUD does not support " + ds_type)
        require_temp_schema(schema, allow_non_temp)
        rng = random.Random(seed)
        tables = self.profile_tables(profile)
        conn = self._connect(ds, password, user=kwargs.get("user"), host_type=kwargs.get("host_type"), host=kwargs.get("host"))
        stats = {table: {"insert": 0, "update": 0, "delete": 0, "skippedDuplicate": 0} for table in tables}
        changed = 0
        try:
            with conn.cursor() as cur:
                for i in range(1, rounds + 1):
                    table = rng.choice(tables)
                    action = rng.choice(("insert", "update", "delete"))
                    marker = "crud-" + str(seed) + "-" + str(i)
                    try:
                        affected = self._crud_one(cur, schema, table, action, marker, i, rng)
                    except Exception as e:
                        if self._is_duplicate_key_error(e):
                            stats[table]["skippedDuplicate"] += 1
                            continue
                        raise
                    stats[table][action] += 1
                    changed += int(affected or 0)
        finally:
            conn.close()
        return {"schema": schema, "profile": profile, "rounds": rounds, "seed": seed, "changedRows": changed, "stats": stats, "ok": changed > 0}

    def _is_duplicate_key_error(self, error):
        code = getattr(error, "args", [None])[0] if getattr(error, "args", None) else None
        text = str(error).lower()
        return code in (1022, 1062) or "duplicate entry" in text or "duplicate key" in text

    def _crud_one(self, cur, schema, table, action, marker, i, rng):
        if table == "pk_int_table":
            key = 100000 + i
            if action == "delete":
                cur.execute("DELETE FROM " + qname(schema, table) + " WHERE id = %s", (rng.randint(1, 50),))
            elif action == "update":
                cur.execute("UPDATE " + qname(schema, table) + " SET payload = %s WHERE id = %s", (marker, rng.randint(1, 50)))
            else:
                cur.execute(
                    "INSERT INTO "
                    + qname(schema, table)
                    + " (id, code, amount, payload) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE payload = VALUES(payload)",
                    (key, marker, i * 2.22, marker),
                )
            return cur.rowcount
        elif table == "pk_int_auto_table":
            if action == "delete":
                cur.execute("DELETE FROM " + qname(schema, table) + " WHERE id = %s", (rng.randint(1, 50),))
            elif action == "update":
                cur.execute("UPDATE " + qname(schema, table) + " SET payload = %s WHERE id = %s", (marker, rng.randint(1, 50)))
            else:
                cur.execute(
                    "INSERT INTO " + qname(schema, table) + " (code, amount, payload) VALUES (%s, %s, %s)",
                    (marker, i * 2.22, marker),
                )
            return cur.rowcount
        elif table == "pk_varchar_table":
            key = "crud_vk_" + str(i)
            if action == "delete":
                cur.execute("DELETE FROM " + qname(schema, table) + " WHERE id = %s", ("vk_" + str(rng.randint(1, 50)),))
            elif action == "update":
                cur.execute("UPDATE " + qname(schema, table) + " SET payload = %s WHERE id = %s", (marker, "vk_" + str(rng.randint(1, 50))))
            else:
                cur.execute(
                    "INSERT INTO "
                    + qname(schema, table)
                    + " (id, code, amount, payload) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE payload = VALUES(payload)",
                    (key, marker, i * 2.22, marker),
                )
            return cur.rowcount
        elif table == "pk_timestamp_table":
            base = datetime(2026, 1, 1, 0, 0, 0)
            crud_base = datetime(2027, 1, 1, 0, 0, 0)
            if action == "delete":
                pk_value = (base + timedelta(seconds=rng.randint(1, 50))).strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    "DELETE FROM " + qname(schema, table) + " WHERE id = %s",
                    (pk_value,),
                )
            elif action == "update":
                pk_value = (base + timedelta(seconds=rng.randint(1, 50))).strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    "UPDATE " + qname(schema, table) + " SET payload = %s WHERE id = %s",
                    (marker, pk_value),
                )
            else:
                pk_value = (crud_base + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    "INSERT INTO "
                    + qname(schema, table)
                    + " (id, code, amount, payload) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE payload = VALUES(payload)",
                    (pk_value, marker, i * 2.22, marker),
                )
            return cur.rowcount
        return 0

    def _columns(self, cur, schema, table):
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
            ORDER BY ORDINAL_POSITION
            """,
            (schema, table),
        )
        return [row[0] for row in cur.fetchall()]

    def _table_digest(self, cur, schema, table):
        columns = self._columns(cur, schema, table)
        if not columns:
            return {"exists": False, "rows": 0, "digest": None, "columns": []}
        col_sql = ", ".join(quote_ident(c) for c in columns)
        order_sql = ", ".join(quote_ident(c) for c in columns)
        cur.execute("SELECT " + col_sql + " FROM " + qname(schema, table) + " ORDER BY " + order_sql)
        digest = hashlib.sha256()
        count = 0
        for row in cur.fetchall():
            digest.update(json.dumps([str(item) if item is not None else None for item in row], ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            digest.update(b"\n")
            count += 1
        return {"exists": True, "rows": count, "digest": digest.hexdigest(), "columns": columns}

    def _table_count(self, cur, schema, table):
        columns = self._columns(cur, schema, table)
        if not columns:
            return {"exists": False, "rows": 0}
        cur.execute("SELECT COUNT(*) FROM " + qname(schema, table))
        row = cur.fetchone()
        return {"exists": True, "rows": row[0] if row else None}

    def _primary_key_columns(self, cur, schema, table):
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA=%s
              AND TABLE_NAME=%s
              AND CONSTRAINT_NAME='PRIMARY'
            ORDER BY ORDINAL_POSITION
            """,
            (schema, table),
        )
        return [row[0] for row in cur.fetchall()]

    def compare_datasets(self, source_ds, target_ds, source_password, target_password, source_schema, target_schema, profile, allow_non_temp, **kwargs):
        source_type = normalize_ds_type(source_ds.get("dataSourceType"))
        target_type = normalize_ds_type(target_ds.get("dataSourceType"))
        if not self.supports_source(source_type):
            raise AdapterCapabilityError("MySQL-family compare source does not support " + source_type)
        if not self.supports_target(target_type):
            raise AdapterCapabilityError("MySQL-family compare target does not support " + target_type)
        require_temp_schema(source_schema, allow_non_temp)
        require_temp_schema(target_schema, allow_non_temp)
        source_conn = self._connect(
            source_ds,
            source_password,
            user=kwargs.get("source_user"),
            host_type=kwargs.get("source_host_type"),
            host=kwargs.get("source_host"),
        )
        target_conn = self._connect(
            target_ds,
            target_password,
            user=kwargs.get("target_user"),
            host_type=kwargs.get("target_host_type"),
            host=kwargs.get("target_host"),
        )
        check_mode = kwargs.get("check_mode") or "count"
        if check_mode not in ("count", "digest"):
            raise ValueError("unsupported check mode: " + str(check_mode))
        result = {
            "sourceSchema": source_schema,
            "targetSchema": target_schema,
            "profile": profile,
            "checkMode": check_mode,
            "tables": [],
            "ignoredTables": [],
            "ok": True,
        }
        try:
            with source_conn.cursor() as src_cur, target_conn.cursor() as dst_cur:
                for table in kwargs.get("tables") or self.profile_tables(profile):
                    if check_mode == "digest":
                        src = self._table_digest(src_cur, source_schema, table)
                        dst = self._table_digest(dst_cur, target_schema, table)
                    else:
                        src = self._table_count(src_cur, source_schema, table)
                        dst = self._table_count(dst_cur, target_schema, table)
                    primary_key_columns = self._primary_key_columns(src_cur, source_schema, table) if src.get("exists") else []
                    ok = src == dst and snapshots_equal(src, dst, check_mode)
                    table_result = {
                        "table": table,
                        "ok": ok,
                        "source": src,
                        "target": dst,
                        "primaryKeyColumns": primary_key_columns,
                    }
                    result["tables"].append(table_result)
                    if not ok:
                        result["ok"] = False
        finally:
            source_conn.close()
            target_conn.close()
        return result

    def table_snapshot(self, ds, password, schema, table, check_mode, allow_non_temp, **kwargs):
        require_temp_schema(schema, allow_non_temp)
        conn = self._connect(
            ds,
            password,
            user=kwargs.get("user"),
            host_type=kwargs.get("host_type"),
            host=kwargs.get("host"),
        )
        try:
            with conn.cursor() as cur:
                if check_mode == "digest":
                    return self._table_digest(cur, schema, table)
                if check_mode == "count":
                    return self._table_count(cur, schema, table)
                raise ValueError("unsupported check mode: " + str(check_mode))
        finally:
            conn.close()
