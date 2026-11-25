import json
import unittest
from unittest.mock import MagicMock, patch

from test_auth import run_cli
from cc_console import autotest
from cc_console.db_adapters import adapter_for_type


class MongoAdapterTest(unittest.TestCase):
    def test_dataset_commands_use_the_selected_mongo_database(self):
        adapter = adapter_for_type("MongoDB")
        client = MagicMock()
        source, target = MagicMock(), MagicMock()
        source_name, target_name = "cc_auto_mongo_source", "cc_auto_document_target"
        client.__getitem__.side_effect = {source_name: source, target_name: target}.__getitem__
        connection = ["--base-url", "https://console.example", "--cookie", "fixture"]

        def command(name, *options):
            status, output, errors = run_cli(name, *connection, *options)
            self.assertEqual(0, status, errors + output)
            return json.loads(output)

        def datasource(_client, ds_id):
            return {"dataSourceType": {1: "MongoDB", 2: "DocumentDB"}[ds_id]}

        src = ["--data-source-id", "1", "--schema", source_name, "--password", "fixture"]
        dst = ["--data-source-id", "2", "--schema", target_name, "--password", "fixture"]
        with patch.object(autotest, "query_datasource", side_effect=datasource), patch.object(adapter, "_client", return_value=client):
            seeded = command("autotest-init", *src, "--rows", "1")
            prepared = command("autotest-prepare-target", *dst)
            src_table, dst_table = seeded["tables"][0], prepared["tables"][0]
            source.create_collection.assert_any_call(src_table)
            target.create_collection.assert_any_call(dst_table)
            self.assertTrue(source[src_table].insert_many.called)
            self.assertEqual(1, command("autotest-crud", *src, "--rounds", "1")["changedRows"])
            source.list_collection_names.return_value = seeded["tables"]
            target.list_collection_names.return_value = prepared["tables"]
            for collection in (source[src_table], target[dst_table]):
                collection.count_documents.return_value = 2
                collection.find.return_value = [{"id": "first"}, {"id": "second"}]
            for mode in ("count", "digest"):
                result = command("autotest-check", "--source-ds-id", "1", "--target-ds-id", "2",
                                 "--source-schema", source_name, "--target-schema", target_name,
                                 "--source-password", "fixture", "--target-password", "fixture",
                                 "--table-map", src_table + "=" + dst_table, "--check-mode", mode)
                self.assertTrue(result["ok"])
                self.assertEqual(2, result["tables"][0]["source"]["rows"])
            command("autotest-cleanup-dataset", *dst, "--table", dst_table)
            target[dst_table].drop.assert_called_once()
            source[src_table].drop.assert_not_called()

    def test_mongo_cleanup_checks_namespace_before_opening_a_client(self):
        adapter = adapter_for_type("DocumentDB")
        with patch.object(adapter, "_client") as client:
            with self.assertRaisesRegex(ValueError, "non-temp schema"):
                adapter.cleanup_dataset({}, "fixture", "customer", False, tables=["cc_auto_probe"])
            client.assert_not_called()

    def test_faker_does_not_count_a_zero_row_write(self):
        adapter = adapter_for_type("MongoDB")
        with patch.object(adapter, "_write_records", return_value=0):
            result = adapter.faker_crud({}, "fixture", "cc_auto_source", 1, adapter.default_profile, 5, False)
        self.assertEqual(0, result["changedRows"])
        self.assertFalse(result["ok"])
