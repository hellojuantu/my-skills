from cc_console.datasource import choose_test_host, default_port

from .base import parse_host_port
from .object_common import NamespacedObjectAdapter


class MongoFamilyAdapter(NamespacedObjectAdapter):
    name = "mongo-family"
    data_source_types = ("MongoDB", "DocumentDB")
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("pymongo",)
    install_commands = ("python3 -m pip install pymongo",)
    default_profile = "mongo-core"
    data_model = "document-collection"
    object_label = "mongo"

    def _client(self, ds, password, **kwargs):
        self.require_dependencies()
        from pymongo import MongoClient

        host_value, _host_type = choose_test_host(ds, kwargs.get("host_type"), kwargs.get("host"))
        host, port = parse_host_port(host_value, default_port("MongoDB"))
        user = kwargs.get("user") or ds.get("accountName") or None
        auth = ""
        if user:
            auth = str(user) + ":" + str(password or "") + "@"
        return MongoClient("mongodb://" + auth + str(host) + ":" + str(port) + "/?authSource=admin", serverSelectionTimeoutMS=10000)

    def _db(self, client, kwargs):
        return client[kwargs.get("schema") or kwargs.get("database") or "cc_auto_doc"]

    def _create_object(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        self._db(client, kwargs).create_collection(table) if table not in self._db(client, kwargs).list_collection_names() else None
        client.close()

    def _delete_object(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        self._db(client, kwargs)[table].drop()
        client.close()

    def _object_exists(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        try:
            return table in self._db(client, kwargs).list_collection_names()
        finally:
            client.close()

    def _write_records(self, ds, password, table, records, **kwargs):
        client = self._client(ds, password, **kwargs)
        try:
            docs = [dict(record, _id=record["id"]) for record in records]
            if docs:
                self._db(client, kwargs)[table].insert_many(docs, ordered=False)
            return len(docs)
        finally:
            client.close()

    def _count_records(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        try:
            return self._db(client, kwargs)[table].count_documents({})
        finally:
            client.close()

    def _read_records(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        try:
            docs = []
            for doc in self._db(client, kwargs)[table].find({}, sort=[("_id", 1)]):
                doc.pop("_id", None)
                docs.append(doc)
            return docs
        finally:
            client.close()

    def init_source_dataset(self, ds, password, schema, rows, profile, drop_existing, allow_non_temp, **kwargs):
        kwargs["schema"] = schema
        return super().init_source_dataset(ds, password, schema, rows, profile, drop_existing, allow_non_temp, **kwargs)

    def prepare_target_dataset(self, ds, password, schema, drop_existing, allow_non_temp, **kwargs):
        kwargs["schema"] = schema
        return super().prepare_target_dataset(ds, password, schema, drop_existing, allow_non_temp, **kwargs)

    def cleanup_dataset(self, ds, password, schema, allow_non_temp, **kwargs):
        kwargs["schema"] = schema
        return super().cleanup_dataset(ds, password, schema, allow_non_temp, **kwargs)

    def faker_crud(self, ds, password, schema, rounds, profile, seed, allow_non_temp, **kwargs):
        kwargs["schema"] = schema
        return super().faker_crud(ds, password, schema, rounds, profile, seed, allow_non_temp, **kwargs)

    def table_snapshot(self, ds, password, schema, table, check_mode, allow_non_temp, **kwargs):
        kwargs["schema"] = schema
        return super().table_snapshot(ds, password, schema, table, check_mode, allow_non_temp, **kwargs)


class DynamoDbFamilyAdapter(NamespacedObjectAdapter):
    name = "dynamodb-family"
    data_source_types = ("DynamoDB",)
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("boto3",)
    install_commands = ("python3 -m pip install boto3",)
    default_profile = "dynamodb-core"
    data_model = "document-table"
    object_label = "dynamo"

    def _resource(self, ds, password, **kwargs):
        self.require_dependencies()
        import boto3

        host_value, _host_type = choose_test_host(ds, kwargs.get("host_type"), kwargs.get("host"))
        endpoint = None
        if host_value:
            host, port = parse_host_port(host_value, default_port("DynamoDB"))
            endpoint = "http://" + str(host) + ":" + str(port)
        return boto3.resource(
            "dynamodb",
            endpoint_url=endpoint,
            aws_access_key_id=kwargs.get("user") or ds.get("accountName") or "dummy",
            aws_secret_access_key=password or "dummy",
            region_name=ds.get("region") or kwargs.get("region") or "us-east-1",
        )

    def _create_object(self, ds, password, table, **kwargs):
        resource = self._resource(ds, password, **kwargs)
        try:
            resource.Table(table).load()
            return True
        except Exception:
            resource.create_table(
                TableName=table,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            waiter = resource.meta.client.get_waiter("table_exists")
            waiter.wait(TableName=table, WaiterConfig={"Delay": 1, "MaxAttempts": 30})
            return True

    def _delete_object(self, ds, password, table, **kwargs):
        resource = self._resource(ds, password, **kwargs)
        try:
            resource.Table(table).delete()
            waiter = resource.meta.client.get_waiter("table_not_exists")
            waiter.wait(TableName=table, WaiterConfig={"Delay": 1, "MaxAttempts": 30})
        except Exception:
            pass

    def _object_exists(self, ds, password, table, **kwargs):
        resource = self._resource(ds, password, **kwargs)
        try:
            resource.Table(table).load()
            return True
        except Exception:
            return False

    def _write_records(self, ds, password, table, records, **kwargs):
        resource = self._resource(ds, password, **kwargs)
        ddb_table = resource.Table(table)
        with ddb_table.batch_writer(overwrite_by_pkeys=["id"]) as batch:
            for record in records:
                batch.put_item(Item=record)
        return len(records)

    def _count_records(self, ds, password, table, **kwargs):
        resource = self._resource(ds, password, **kwargs)
        response = resource.Table(table).scan(Select="COUNT")
        total = int(response.get("Count") or 0)
        while response.get("LastEvaluatedKey"):
            response = resource.Table(table).scan(Select="COUNT", ExclusiveStartKey=response["LastEvaluatedKey"])
            total += int(response.get("Count") or 0)
        return total

    def _read_records(self, ds, password, table, **kwargs):
        resource = self._resource(ds, password, **kwargs)
        response = resource.Table(table).scan()
        items = list(response.get("Items") or [])
        while response.get("LastEvaluatedKey"):
            response = resource.Table(table).scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items") or [])
        return sorted(items, key=lambda item: item.get("id", ""))
