from cc_console.datasource import choose_test_host, default_port

from .base import AdapterCapabilityError, parse_host_port
from .object_common import NamespacedObjectAdapter


class ElasticSearchFamilyAdapter(NamespacedObjectAdapter):
    name = "elasticsearch-family"
    data_source_types = ("ElasticSearch",)
    source_data_types = data_source_types
    target_data_types = data_source_types
    driver_modules = ("elasticsearch",)
    install_commands = ("python3 -m pip install elasticsearch",)
    default_profile = "elasticsearch-core"
    data_model = "search-index"
    object_label = "es"
    object_name_max_length = 255

    def _client(self, ds, password, **kwargs):
        self.require_dependencies()
        from elasticsearch import Elasticsearch

        host_value, _host_type = choose_test_host(ds, kwargs.get("host_type"), kwargs.get("host"))
        host, port = parse_host_port(host_value, default_port("ElasticSearch"))
        scheme = "https" if str(ds.get("useSSL") or "").lower() == "true" else "http"
        user = kwargs.get("user") or ds.get("accountName") or None
        if user:
            return Elasticsearch([{"host": host, "port": port, "scheme": scheme}], basic_auth=(user, password or ""))
        return Elasticsearch([{"host": host, "port": port, "scheme": scheme}])

    def _create_object(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        if not client.indices.exists(index=table):
            client.indices.create(index=table, mappings={"properties": {"id": {"type": "keyword"}, "code": {"type": "keyword"}, "amount": {"type": "double"}, "payload": {"type": "text"}, "updated_at": {"type": "date"}}})
        return True

    def _delete_object(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        if client.indices.exists(index=table):
            client.indices.delete(index=table)
        return True

    def _object_exists(self, ds, password, table, **kwargs):
        return bool(self._client(ds, password, **kwargs).indices.exists(index=table))

    def _write_records(self, ds, password, table, records, **kwargs):
        client = self._client(ds, password, **kwargs)
        for record in records:
            client.index(index=table, id=record["id"], document=record)
        client.indices.refresh(index=table)
        return len(records)

    def _count_records(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        if not client.indices.exists(index=table):
            return 0
        response = client.count(index=table)
        if response.get("_shards", {}).get("failed") or type(response.get("count")) is not int:
            raise AdapterCapabilityError(f"Elasticsearch returned an incomplete count for {table}")
        return response["count"]

    def _read_records(self, ds, password, table, **kwargs):
        client = self._client(ds, password, **kwargs)
        if not client.indices.exists(index=table):
            return []
        response = client.search(index=table, query={"match_all": {}}, sort=["id:asc"], size=10000, track_total_hits=True)
        hits = response["hits"]
        total = hits["total"]
        if isinstance(total, dict):
            total = total["value"] if total.get("relation") == "eq" else None
        if (response.get("timed_out") or response.get("terminated_early") or response.get("_shards", {}).get("failed")
                or type(total) is not int or total != len(hits["hits"])):
            raise AdapterCapabilityError(f"Elasticsearch returned an incomplete digest for {table}. Use count or CloudCanal CHECK.")
        return [hit["_source"] for hit in hits["hits"]]
