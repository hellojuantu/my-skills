import hashlib
import json
from datetime import datetime

from .base import AdapterCapabilityError, DatabaseAdapter, require_temp_schema, safe_object_name


CORE_OBJECT_COUNT = 4


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def object_record(table, index, marker="seed"):
    return {
        "id": table + "_" + str(index),
        "code": "code_" + str(index),
        "amount": round(index * 1.11, 2),
        "payload": marker + "-" + table + "-" + str(index),
        "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


def digest_values(values):
    digest = hashlib.sha256()
    count = 0
    for value in values:
        digest.update(json_bytes(value))
        digest.update(b"\n")
        count += 1
    return count, digest.hexdigest()


class NamespacedObjectAdapter(DatabaseAdapter):
    object_label = "obj"
    object_name_max_length = 63
    can_init_source = True
    can_prepare_target = True
    can_cleanup = True
    can_faker_crud = True
    can_compare = True

    def _check_profile(self, profile):
        if profile != self.default_profile:
            raise AdapterCapabilityError("unsupported " + self.name + " profile: " + str(profile))

    def profile_tables(self, profile):
        self._check_profile(profile)
        prefix = safe_object_name(self.name.replace("-family", ""), self.object_label, max_length=32)
        return [safe_object_name(prefix, i, max_length=self.object_name_max_length) for i in range(1, CORE_OBJECT_COUNT + 1)]

    def profile_tables_for_namespace(self, profile, namespace):
        self._check_profile(profile)
        prefix = safe_object_name(namespace or "cc_auto", self.object_label, max_length=max(16, self.object_name_max_length - 8))
        return [safe_object_name(prefix, i, max_length=self.object_name_max_length) for i in range(1, CORE_OBJECT_COUNT + 1)]

    def _records(self, table, rows, marker="seed"):
        return [object_record(table, i, marker=marker) for i in range(1, rows + 1)]

    def init_source_dataset(self, ds, password, schema, rows, profile, drop_existing, allow_non_temp, **kwargs):
        require_temp_schema(schema, allow_non_temp)
        tables = self.profile_tables_for_namespace(profile, schema)
        for table in tables:
            if drop_existing:
                self._delete_object(ds, password, table, **kwargs)
            self._create_object(ds, password, table, **kwargs)
            self._write_records(ds, password, table, self._records(table, rows), **kwargs)
        return {"schema": schema, "profile": profile, "tables": tables, "seedRowsPerObject": rows}

    def prepare_target_dataset(self, ds, password, schema, drop_existing, allow_non_temp, **kwargs):
        require_temp_schema(schema, allow_non_temp)
        tables = kwargs.get("tables") or self.profile_tables_for_namespace(self.default_profile, schema)
        for table in tables:
            if drop_existing:
                self._delete_object(ds, password, table, **kwargs)
            self._create_object(ds, password, table, **kwargs)
        return {"schema": schema, "tables": tables}

    def cleanup_dataset(self, ds, password, schema, allow_non_temp, **kwargs):
        require_temp_schema(schema, allow_non_temp)
        tables = kwargs.get("tables") or self.profile_tables_for_namespace(self.default_profile, schema)
        for table in tables:
            self._delete_object(ds, password, table, **kwargs)
        return {"schema": schema, "tables": tables, "dropped": True}

    def faker_crud(self, ds, password, schema, rounds, profile, seed, allow_non_temp, **kwargs):
        require_temp_schema(schema, allow_non_temp)
        tables = self.profile_tables_for_namespace(profile, schema)
        stats = {table: {"insert": 0, "update": 0, "delete": 0, "skippedDuplicate": 0} for table in tables}
        changed = 0
        for i in range(1, rounds + 1):
            table = tables[(i - 1) % len(tables)]
            record = object_record(table, seed + i, marker="crud")
            affected = self._write_records(ds, password, table, [record], **kwargs)
            stats[table]["insert"] += int(affected or 1)
            changed += int(affected or 1)
        return {"schema": schema, "profile": profile, "rounds": rounds, "seed": seed, "changedRows": changed, "stats": stats, "ok": changed > 0}

    def table_snapshot(self, ds, password, schema, table, check_mode, allow_non_temp, **kwargs):
        require_temp_schema(schema, allow_non_temp)
        if check_mode == "count":
            return {"exists": self._object_exists(ds, password, table, **kwargs), "rows": self._count_records(ds, password, table, **kwargs)}
        if check_mode == "digest":
            values = self._read_records(ds, password, table, **kwargs)
            count, digest = digest_values(values)
            return {"exists": self._object_exists(ds, password, table, **kwargs), "rows": count, "digest": digest, "columns": ["id", "code", "amount", "payload", "updated_at"]}
        raise ValueError("unsupported check mode: " + str(check_mode))

    def _create_object(self, ds, password, table, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement object create")

    def _delete_object(self, ds, password, table, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement object delete")

    def _object_exists(self, ds, password, table, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement object exists")

    def _write_records(self, ds, password, table, records, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement object write")

    def _count_records(self, ds, password, table, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement object count")

    def _read_records(self, ds, password, table, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement object read")
