import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cc_console import datajob, logview
from cc_console.cli import build_parser
from cc_console.client import ApiError, ConsoleClient


def encoded(*parts):
    obj = None
    for part in parts:
        obj = datajob.compare_obj(part, obj)
    return json.dumps(obj)


def group(db, *tables):
    return {"db": db, "tables": [{"table": name, "columns": [{"column": "id"}]} for name in tables]}


class JobConsole(ConsoleClient):
    def __init__(self):
        super().__init__("http://console.test")
        self.source = [group("sales", "old", "keep"), group("archive", "old")]
        self.target = [group("warehouse", "orders", "keep"), group("archive", "old")]
        self.processors = [{"processorConfigType": "CUSTOM_PKG_PROCESSOR", "allProcessorContextJson": "{}"}]
        self.mapping = [
            {"method": "DB_DB", "serializeMapping": {encoded("sales"): encoded("warehouse")}},
            {"method": "TABLE_TABLE", "serializeMapping": {encoded("sales", "old"): encoded("warehouse", "orders")}},
            {"method": "COLUMN_COLUMN", "serializeMapping": {
                encoded("sales", "old", "id"): encoded("warehouse", "orders", "order_id"),
                encoded("archive", "old", "id"): encoded("archive", "old", "id"),
            }},
        ]
        self.job = {
            "dataJobId": 21, "dataJobName": "orders", "sourceDsVO": {"dataSourceType": "MySQL"},
            "targetDsVO": {"dataSourceType": "MySQL"}, "processorConfigListJson": json.dumps(self.processors),
            "dataTasks": [{"dataTaskType": "FULL", "dataTaskId": 123, "dataTaskStatus": "RUNNING"}],
        }
        self.requests = []
        self.states = []
        self.edit = None

    def post_multipart(self, path, parts):
        self.requests.append(path)
        if path != datajob.CREATE_JOB_PATH:
            raise AssertionError(path)
        return {"code": "1", "data": 21}

    def post_json(self, path, payload):
        self.requests.append(path)
        if path == datajob.QUERY_JOB_PATH:
            self.assert_id(payload)
            if self.states:
                self.job.update(self.states.pop(0))
            result = self.job
        elif path == datajob.QUERY_JOB_SCHEMA_PATH:
            result = {"sourceSchema": json.dumps(self.source), "targetSchema": json.dumps(self.target), "mappingConfig": json.dumps(self.mapping),
                      "dstDsCaseSensitive": False}
        elif path == datajob.SCHEMA_MAPPING_RULE_PATH:
            result = {}
        elif path == datajob.UPDATE_TRANSFER_OBJECT_PATH:
            self.edit = payload
            result = None
        elif path == datajob.START_JOB_PATH:
            assert payload == {"jobId": 21, "dataJobName": "orders"}
            assert self.job["lifeCycleState"] == "CREATED"
            result = None
        else:
            raise AssertionError(path)
        return {"code": "1", "data": result}

    def assert_id(self, payload):
        assert payload == {"jobId": 21}


class JobMutationTest(unittest.TestCase):
    def setUp(self):
        self.client = JobConsole()
        self.parser = build_parser()

    def edit(self, *options):
        args = self.parser.parse_args(["edit-job", "--job-id", "21", *options])
        with contextlib.redirect_stdout(io.StringIO()):
            datajob.edit_job_cmd(args, self.client)
        return self.client.edit

    def test_remove_uses_saved_mapping_and_keeps_unrelated_objects_and_processors(self):
        payload = self.edit("--remove-table", "sales.old")
        self.assertEqual([group("sales", "keep"), group("archive", "old")], json.loads(payload["srcSchemaWithoutAdd"]))
        self.assertEqual([group("warehouse", "keep"), group("archive", "old")], json.loads(payload["dstSchemaWithoutAdd"]))
        self.assertEqual([group("sales", "old")], json.loads(payload["reduceConfig"]))
        mapping = json.loads(payload["mappingConfigWithoutAdd"])
        self.assertEqual(self.client.mapping[0], mapping[0])
        self.assertEqual({}, mapping[1]["serializeMapping"])
        self.assertEqual({encoded("archive", "old", "id"): encoded("archive", "old", "id")}, mapping[2]["serializeMapping"])
        self.assertEqual(self.client.processors, payload["processorConfsWithoutAdd"])

    def test_removing_one_of_two_sources_for_a_target_preserves_shared_target(self):
        self.client.mapping[1]["serializeMapping"][encoded("sales", "keep")] = encoded("warehouse", "orders")
        result = self.edit("--remove-table", "sales.old")
        self.assertEqual(self.client.target, json.loads(result["dstSchemaWithoutAdd"]))

    def test_existing_pattern_cannot_silently_resubscribe_removed_table(self):
        self.client.source = [group("sales", "orders_live", "orders_.*")]
        self.client.source[0]["tables"][1]["pattern"] = True
        self.client.target = [group("sales", "orders_live")]
        self.client.mapping = []
        with self.assertRaisesRegex(ValueError, "subscription edit containing a pattern"):
            self.edit("--remove-table", "sales.orders_live")
        self.assertIsNone(self.client.edit)

    def test_generated_database_mapping_cannot_drop_shared_target(self):
        self.client.job["dstDsCaseSensitive"] = True
        self.client.source = [group("A", "orders"), group("a", "orders")]
        self.client.target = [group("A", "orders")]
        self.client.mapping = [{"method": "DB_DB", "commonGenRule": "TO_UPPER_CASE"}]
        with self.assertRaisesRegex(ValueError, "generated database/schema mapping"):
            self.edit("--remove-table", "A.orders")
        self.assertIsNone(self.client.edit)

    def test_case_sensitive_target_uses_job_detail_setting(self):
        self.client.job["dstDsCaseSensitive"] = True
        self.client.source = self.client.target = [group("sales", "Orders", "orders")]
        self.client.mapping = []
        result = self.edit("--remove-table", "sales.Orders")
        self.assertEqual([group("sales", "orders")], json.loads(result["dstSchemaWithoutAdd"]))

    def test_database_topic_is_shared_by_retained_tables(self):
        self.client.job["targetDsVO"]["dataSourceType"] = "Pulsar"
        self.client.source = [group("sales", "orders", "invoices")]
        self.client.target = [{"topic": "orders"}]
        self.client.mapping = [{"method": "DB_TOPIC", "serializeMapping": {encoded("sales"): encoded("orders")}}]
        result = self.edit("--remove-table", "sales.orders")
        self.assertEqual(self.client.mapping, json.loads(result["mappingConfigWithoutAdd"]))
        self.assertEqual(self.client.target, json.loads(result["dstSchemaWithoutAdd"]))

    def test_source_must_be_uniquely_subscribed(self):
        for name in ("old", "missing"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "matches [02] subscribed"):
                self.edit("--remove-table", name)
        self.assertIsNone(self.client.edit)

    def test_manual_fields_override_generated_reduction_and_allow_clearing_processors(self):
        self.client.mapping[1]["serializeMapping"].clear()
        with self.assertRaisesRegex(ValueError, "cannot match destination"):
            self.edit("--remove-table", "sales.old")
        result = self.edit("--remove-table", "sales.old", "--target-schema-without-add-json", "[]",
                           "--reduce-config-json", '[{"custom":true}]', "--processor-without-add-json", "[]")
        self.assertEqual([], json.loads(result["dstSchemaWithoutAdd"]))
        self.assertEqual([{"custom": True}], json.loads(result["reduceConfig"]))
        self.assertEqual([], result["processorConfsWithoutAdd"])

    def test_unmaterialized_camel_case_mapping_needs_explicit_target_override(self):
        self.client.source = [group("sales", "id_a", "idA")]
        self.client.target = [group("sales", "idA")]
        self.client.mapping = [{"method": "TABLE_TABLE", "commonGenRule": "TO_CAMEL_FORMAT"}]
        with self.assertRaisesRegex(ValueError, "TO_CAMEL_FORMAT"):
            self.edit("--remove-table", "sales.id_a")
        result = self.edit("--remove-table", "sales.id_a", "--target-schema-without-add-json", json.dumps(self.client.target))
        self.assertEqual(self.client.target, json.loads(result["dstSchemaWithoutAdd"]))

    def test_legacy_null_processor_list_accepts_an_unrelated_edit(self):
        self.client.job["processorConfigListJson"] = "null"
        result = self.edit("--source-schema-without-add-json", json.dumps(self.client.source))
        self.assertEqual([], result["processorConfsWithoutAdd"])

    def test_oracle_cleanup_uses_mapped_tablespace_and_target_table(self):
        self.client.job["targetDsVO"]["dataSourceType"] = "Oracle"
        self.client.target = []
        self.client.mapping[1]["serializeMapping"][encoded("sales", "old")] = encoded("ORA", "APP", "ORDERS")
        result = self.edit("--remove-table", "sales.old")
        oracle_db, = json.loads(result["targetReduceConfig"])
        self.assertEqual("ORA", oracle_db["db"])
        space, = oracle_db["tableSpaces"]
        self.assertEqual("APP", space["tableSpace"])
        self.assertEqual(["ORDERS"], [t["table"] for t in space["tables"]])

    def test_oracle_cleanup_keeps_staging_table_shared_across_database_mappings(self):
        self.client.job["targetDsVO"]["dataSourceType"] = "Oracle"
        self.client.source = [group("sales", "old", "keep")]
        self.client.target = []
        self.client.mapping = [{"method": "TABLE_TABLE", "serializeMapping": {
            encoded("sales", "old"): encoded("PDB1", "USR", "T"),
            encoded("sales", "keep"): encoded("PDB2", "USR", "T"),
        }}]
        result = self.edit("--remove-table", "sales.old")
        self.assertNotIn("targetReduceConfig", result)

    def create(self, *options):
        args = self.parser.parse_args(["create-job", "--source-ds-id", "1", "--target-ds-id", "2", *options])
        with patch.object(datajob, "build_datajob_payload", return_value={}):
            return datajob.create_datajob_cmd(args, self.client)

    def test_incompatible_precheck_options_touch_no_endpoint(self):
        with self.assertRaisesRegex(ValueError, "--precheck-only"):
            self.create("--skip-precheck", "--precheck-only")
        self.assertEqual([], self.client.requests)

    def test_start_waits_for_async_completion(self):
        self.client.states = [{"lifeCycleState": "CREATING", "consoleTaskState": "RUNNING"}, {"lifeCycleState": "CREATED", "consoleTaskState": "SUCCESS"}]
        with patch.object(datajob.time, "sleep"), contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(0, self.create("--skip-precheck", "--start-after-create"))
        self.assertIn("id=21", stdout.getvalue())
        self.assertEqual([datajob.CREATE_JOB_PATH] + [datajob.QUERY_JOB_PATH] * 3 + [datajob.START_JOB_PATH], self.client.requests)

    def test_failed_async_creation_keeps_id_and_never_starts(self):
        self.client.states = [{"lifeCycleState": "CREATING", "consoleTaskState": "FAILED"}]
        with contextlib.redirect_stdout(io.StringIO()) as stdout, self.assertRaisesRegex(ApiError, "console task failed"):
            self.create("--skip-precheck", "--start-after-create")
        self.assertIn("id=21", stdout.getvalue())
        self.assertNotIn(datajob.START_JOB_PATH, self.client.requests)

    def test_explicit_stage_must_exist_and_automatic_selection_still_works(self):
        self.client.job["dataTaskState"] = "CHECK"
        args = self.parser.parse_args(["tail-task-log", "--job-id", "21", "--task-type", "CHECK"])
        with self.assertRaisesRegex(ValueError, "CHECK not found for jobId 21"):
            logview.tail_task_log_cmd(args, self.client)
        self.assertEqual(123, logview.resolve_task_id(self.client, 21))
        self.assertEqual(123, logview.resolve_task_id(self.client, 21, task_type="FULL"))
