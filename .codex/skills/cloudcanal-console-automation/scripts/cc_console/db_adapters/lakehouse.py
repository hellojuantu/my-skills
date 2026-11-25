import json

from .object_common import NamespacedObjectAdapter, json_bytes
from .rdb import DbApiRdbAdapter


class RoutedObjectAdapter(NamespacedObjectAdapter):
    can_init_source = False
    can_prepare_target = False
    can_cleanup = False
    can_faker_crud = False
    can_compare = False

    def capabilities(self):
        result = super().capabilities()
        result["profileTables"] = False
        return result

    def profile_tables(self, profile):
        self._check_profile(profile)
        return []

    def profile_tables_for_namespace(self, profile, namespace):
        return self.profile_tables(profile)


class FsspecObjectAdapter(NamespacedObjectAdapter):
    driver_modules = ("fsspec",)
    install_commands = ("python3 -m pip install fsspec s3fs",)
    object_name_max_length = 180

    def _root(self, ds, **kwargs):
        root = kwargs.get("root") or ds.get("dbName") or ds.get("privateHost") or ds.get("publicHost") or ds.get("host")
        if not root:
            raise ValueError(self.name + " requires an explicit writable fsspec root/host; refusing to use a local fallback path")
        return str(root).rstrip("/")

    def _path(self, ds, table, **kwargs):
        return self._root(ds, **kwargs) + "/" + table + ".jsonl"

    def _fs(self, path):
        self.require_dependencies()
        import fsspec

        return fsspec.core.url_to_fs(path)

    def _create_object(self, ds, password, table, **kwargs):
        path = self._path(ds, table, **kwargs)
        fs, fs_path = self._fs(path)
        parent = fs_path.rsplit("/", 1)[0] if "/" in fs_path else ""
        if parent:
            fs.makedirs(parent, exist_ok=True)
        if not fs.exists(fs_path):
            with fs.open(fs_path, "wb") as f:
                f.write(b"")
        return True

    def _delete_object(self, ds, password, table, **kwargs):
        path = self._path(ds, table, **kwargs)
        fs, fs_path = self._fs(path)
        if fs.exists(fs_path):
            fs.rm(fs_path)
        return True

    def _object_exists(self, ds, password, table, **kwargs):
        path = self._path(ds, table, **kwargs)
        fs, fs_path = self._fs(path)
        return fs.exists(fs_path)

    def _write_records(self, ds, password, table, records, **kwargs):
        path = self._path(ds, table, **kwargs)
        fs, fs_path = self._fs(path)
        parent = fs_path.rsplit("/", 1)[0] if "/" in fs_path else ""
        if parent:
            fs.makedirs(parent, exist_ok=True)
        with fs.open(fs_path, "ab") as f:
            for record in records:
                f.write(json_bytes(record) + b"\n")
        return len(records)

    def _read_records(self, ds, password, table, **kwargs):
        path = self._path(ds, table, **kwargs)
        fs, fs_path = self._fs(path)
        if not fs.exists(fs_path):
            return []
        records = []
        with fs.open(fs_path, "rb") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line.decode("utf-8")))
        return records

    def _count_records(self, ds, password, table, **kwargs):
        return len(self._read_records(ds, password, table, **kwargs))


class FileFamilyAdapter(FsspecObjectAdapter):
    name = "file-family"
    data_source_types = ("OssFile", "S3File", "SshFile")
    source_data_types = data_source_types
    target_data_types = data_source_types
    install_commands = ("python3 -m pip install fsspec s3fs sshfs ossfs",)
    default_profile = "file-core"
    data_model = "file-object"
    object_label = "file"


class HostedFileFamilyAdapter(RoutedObjectAdapter):
    name = "hosted-file-family"
    data_source_types = ("GoogleDrive", "Yuque")
    source_data_types = data_source_types
    target_data_types = data_source_types
    default_profile = "hosted-file-core"
    data_model = "hosted-file-object"
    object_label = "file"


class LakehouseFamilyAdapter(RoutedObjectAdapter):
    name = "lakehouse-family"
    data_source_types = ("Hive", "Hudi", "Iceberg", "Paimon", "DeltaLake", "Kudu", "MaxCompute", "DataLakeFormation")
    source_data_types = data_source_types
    target_data_types = data_source_types
    install_commands = (
        "python3 -m pip install pyhive pyarrow kudu-python pyodps deltalake pyiceberg",
    )
    default_profile = "lakehouse-core"
    data_model = "lakehouse-table"
    object_label = "lake"


class TunnelFamilyAdapter(RoutedObjectAdapter):
    name = "tunnel-family"
    data_source_types = ("Tunnel",)
    source_data_types = data_source_types
    target_data_types = data_source_types
    default_profile = "tunnel-core"
    data_model = "tunnel-record"
    object_label = "tunnel"


class SnowflakeFamilyAdapter(DbApiRdbAdapter):
    name = "snowflake-family"
    data_source_types = ("Snowflake",)
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("snowflake.connector",)
    install_commands = ("python3 -m pip install snowflake-connector-python",)
    default_profile = "snowflake-core-4"
    data_model = "rdb-snowflake"
    default_database = None

    def _connect(self, ds, password, user=None, db=None, host_type=None, host=None):
        self.require_dependencies()
        import snowflake.connector

        account = host or ds.get("privateHost") or ds.get("publicHost") or ds.get("account") or ds.get("accountIdentifier")
        return snowflake.connector.connect(
            account=account,
            user=self._account(ds, user),
            password=password,
            database=db or self._ds_database(ds),
            schema=self.default_schema,
            warehouse=ds.get("warehouse") or ds.get("warehouseName"),
        )


class SpannerFamilyAdapter(NamespacedObjectAdapter):
    name = "spanner-family"
    data_source_types = ("Spanner",)
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("google.cloud.spanner",)
    install_commands = ("python3 -m pip install google-cloud-spanner",)
    default_profile = "spanner-core"
    data_model = "rdb-spanner"
    object_label = "spanner"

    def _database(self, ds, **kwargs):
        self.require_dependencies()
        from google.cloud import spanner

        project_id = kwargs.get("project_id") or ds.get("projectId") or ds.get("project")
        instance_id = kwargs.get("instance_id") or ds.get("instanceId")
        database_id = kwargs.get("database_id") or ds.get("databaseName") or ds.get("dbName")
        client = spanner.Client(project=project_id) if project_id else spanner.Client()
        return client.instance(instance_id).database(database_id)

    def _create_object(self, ds, password, table, **kwargs):
        database = self._database(ds, **kwargs)
        ddl = (
            "CREATE TABLE "
            + table
            + " (id STRING(128) NOT NULL, code STRING(64), amount NUMERIC, payload STRING(255), updated_at TIMESTAMP OPTIONS (allow_commit_timestamp=true)) PRIMARY KEY (id)"
        )
        try:
            operation = database.update_ddl([ddl])
            operation.result(120)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise

    def _delete_object(self, ds, password, table, **kwargs):
        database = self._database(ds, **kwargs)
        try:
            operation = database.update_ddl(["DROP TABLE " + table])
            operation.result(120)
        except Exception:
            pass

    def _object_exists(self, ds, password, table, **kwargs):
        try:
            self._count_records(ds, password, table, **kwargs)
            return True
        except Exception:
            return False

    def _write_records(self, ds, password, table, records, **kwargs):
        database = self._database(ds, **kwargs)
        with database.batch() as batch:
            batch.insert_or_update(
                table=table,
                columns=("id", "code", "amount", "payload"),
                values=[(record["id"], record["code"], str(record["amount"]), record["payload"]) for record in records],
            )
        return len(records)

    def _count_records(self, ds, password, table, **kwargs):
        database = self._database(ds, **kwargs)
        with database.snapshot() as snapshot:
            rows = list(snapshot.execute_sql("SELECT COUNT(*) FROM " + table))
            return rows[0][0] if rows else 0

    def _read_records(self, ds, password, table, **kwargs):
        database = self._database(ds, **kwargs)
        with database.snapshot() as snapshot:
            rows = snapshot.execute_sql("SELECT id, code, amount, payload FROM " + table + " ORDER BY id")
            return [{"id": row[0], "code": row[1], "amount": str(row[2]), "payload": row[3]} for row in rows]
