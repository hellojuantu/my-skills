import json

from cc_console.datasource import choose_test_host, default_port

from .base import parse_host_port
from .object_common import NamespacedObjectAdapter, json_bytes


class RedisFamilyAdapter(NamespacedObjectAdapter):
    name = "redis-family"
    data_source_types = ("Redis", "ElastiCache")
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("redis",)
    install_commands = ("python3 -m pip install redis",)
    default_profile = "redis-core"
    data_model = "cache-key"
    object_label = "redis"

    def _client(self, ds, password, **kwargs):
        self.require_dependencies()
        import redis

        host_value, _host_type = choose_test_host(ds, kwargs.get("host_type"), kwargs.get("host"))
        host, port = parse_host_port(host_value, default_port("Redis"))
        db = int(kwargs.get("db") or ds.get("dbName") or 0)
        return redis.Redis(host=host, port=port, db=db, username=kwargs.get("user") or ds.get("accountName") or None, password=password or None, decode_responses=False)

    def _key(self, table, record_id):
        return table + ":" + str(record_id)

    def _create_object(self, ds, password, table, **kwargs):
        return True

    def _delete_object(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        cursor = 0
        pattern = (table + ":*").encode("utf-8")
        while True:
            cursor, keys = client.scan(cursor=cursor, match=pattern, count=500)
            if keys:
                client.delete(*keys)
            if cursor == 0:
                break
        return True

    def _object_exists(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        return bool(client.exists((table + ":__probe__").encode("utf-8")) or client.scan(match=(table + ":*").encode("utf-8"), count=1)[1])

    def _write_records(self, ds, password, table, records, **kwargs):
        client = self._client(ds, password, **kwargs)
        pipe = client.pipeline()
        for record in records:
            pipe.set(self._key(table, record["id"]), json_bytes(record))
        pipe.execute()
        return len(records)

    def _count_records(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        total = 0
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor=cursor, match=(table + ":*").encode("utf-8"), count=500)
            total += len(keys)
            if cursor == 0:
                return total

    def _read_records(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        values = []
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor=cursor, match=(table + ":*").encode("utf-8"), count=500)
            for key in sorted(keys):
                raw = client.get(key)
                if raw is not None:
                    values.append(json.loads(raw.decode("utf-8")))
            if cursor == 0:
                return values


class LindormFamilyAdapter(NamespacedObjectAdapter):
    name = "lindorm-family"
    data_source_types = ("Lindorm",)
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("happybase",)
    install_commands = ("python3 -m pip install happybase",)
    default_profile = "lindorm-core"
    data_model = "wide-column"
    object_label = "lindorm"

    def _connection(self, ds, password, **kwargs):
        self.require_dependencies()
        import happybase

        host_value, _host_type = choose_test_host(ds, kwargs.get("host_type"), kwargs.get("host"))
        host, port = parse_host_port(host_value, default_port("Lindorm") or 9090)
        return happybase.Connection(host=host, port=port)

    def _create_object(self, ds, password, table, **kwargs):
        conn = self._connection(ds, password, **kwargs)
        try:
            if table.encode("utf-8") not in conn.tables():
                conn.create_table(table, {"cf": dict()})
        finally:
            conn.close()

    def _delete_object(self, ds, password, table, **kwargs):
        conn = self._connection(ds, password, **kwargs)
        try:
            if table.encode("utf-8") in conn.tables():
                conn.delete_table(table, disable=True)
        finally:
            conn.close()

    def _object_exists(self, ds, password, table, **kwargs):
        conn = self._connection(ds, password, **kwargs)
        try:
            return table.encode("utf-8") in conn.tables()
        finally:
            conn.close()

    def _write_records(self, ds, password, table, records, **kwargs):
        conn = self._connection(ds, password, **kwargs)
        try:
            htable = conn.table(table)
            batch = htable.batch()
            for record in records:
                batch.put(record["id"].encode("utf-8"), {b"cf:json": json_bytes(record)})
            batch.send()
            return len(records)
        finally:
            conn.close()

    def _count_records(self, ds, password, table, **kwargs):
        return len(self._read_records(ds, password, table, **kwargs))

    def _read_records(self, ds, password, table, **kwargs):
        conn = self._connection(ds, password, **kwargs)
        try:
            htable = conn.table(table)
            values = []
            for _key, data in htable.scan():
                raw = data.get(b"cf:json")
                if raw:
                    values.append(json.loads(raw.decode("utf-8")))
            return values
        finally:
            conn.close()
