import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cc_console import autotest, datajob, datasource
from cc_console.cli import build_parser
from cc_console.client import ConsoleClient
from cc_console.db_adapters import adapter_for_type


class AutotestEvidenceTest(unittest.TestCase):
    def test_kafka_increment_dry_run_keeps_topic_auto_create_flag(self):
        args = build_parser().parse_args([
            "autotest-run", "--source-ds-id", "10", "--target-ds-id", "20", "--cluster-id", "2", "--spec-id", "15",
            "--source-schema", "cc_auto_source", "--target-schema", "cc_auto_target",
            "--source-password", "fixture", "--target-password", "fixture", "--table", "cc_auto_orders",
            "--source-charset", "utf8", "--target-charset", "utf8", "--mode", "increment", "--dry-run",
        ])
        client = ConsoleClient("https://console.example")

        def reply(path, payload):
            data = None
            if path == datasource.QUERY_DS_PATH:
                data = {"dataSourceType": "Kafka" if payload["dataSourceId"] == 10 else "MySQL"}
            elif path == datajob.TRANSFORM_JOB_TYPE_PATH:
                data = {"source": "Kafka", "target": "MySQL", "optionType": {"SYNC": {"Incremental": "true"}}}
            return {"code": "1", "data": data}

        with patch.object(client, "post_json", side_effect=reply), patch.object(client, "post_multipart") as submit:
            run = autotest.run_autotest_pair(args, client)
        self.assertTrue(run["ok"], run.get("error"))
        result = autotest.step_result(run, "create-job")
        self.assertEqual(result["targetAutoCreate"], {"cc_auto_orders": True})
        topic = json.loads(result["payload"]["sourceSchema"])[0]
        self.assertEqual(topic["topic"], "cc_auto_orders")
        self.assertIs(topic["targetAutoCreate"], True)
        submit.assert_not_called()

    def test_sql_adapter_comparison_rejects_two_absent_tables(self):
        postgres = adapter_for_type("PostgreSQL")
        with patch.object(postgres, "table_snapshot", return_value={"exists": False, "rows": 0}):
            report = postgres.compare_datasets({}, {}, "src", "dst", "cc_auto_src", "cc_auto_dst", None, False, tables=["example"])
        self.assertFalse(report["ok"])

    def test_missing_count_row_is_not_evidence_of_an_empty_table(self):
        postgres = adapter_for_type("PostgreSQL")
        connection = Mock()
        connection.cursor.return_value.fetchone.return_value = None
        with patch.object(postgres, "_connect_namespace", return_value=connection):
            report = autotest.compare_with_adapters(
                postgres, postgres, {}, {}, "src", "dst", "cc_auto_src", "cc_auto_dst", None, False, tables=["example"],
            )
        self.assertFalse(report["ok"])

    def test_read_failure_is_visible_in_snapshot_comparison(self):
        postgres = adapter_for_type("PostgreSQL")
        connection = Mock()
        connection.cursor.return_value.execute.side_effect = PermissionError("query denied")
        with patch.object(postgres, "_connect_namespace", return_value=connection):
            report = autotest.compare_with_adapters(
                postgres, postgres, {}, {}, "src", "dst", "customers", "replica", None, False,
                tables=["orders"], read_existing_tables=True,
            )
        self.assertFalse(report["ok"])
        self.assertEqual("query denied", report["tables"][0]["source"]["error"])

    def test_check_wait_queries_child_and_requires_both_metrics(self):
        parent_id, child_id = 21, 32
        client = ConsoleClient("https://console.example")
        for position, expected in (({}, False), ({"loss": 0, "diff": 0}, True), ({"loss": 0, "diff": 5}, False)):
            task = {"dataTaskType": "CHECK", "dataTaskStatus": "COMPLETE", "taskPosition": json.dumps(position)}
            child = {"dataJobId": child_id, "dataTasks": [task], "fsmActive": True}

            def reply(_path, payload):
                job = {"childJobs": [child]} if payload["jobId"] == parent_id else child
                return {"code": "1", "data": job}

            with self.subTest(position=position), patch.object(client, "post_json", side_effect=reply) as query:
                result = autotest.wait_check_child(client, parent_id, 1)
                self.assertTrue(result["complete"])
                self.assertIs(result["ok"], expected)
                self.assertEqual(result["children"][0]["jobId"], child_id)
                self.assertEqual(query.call_args.args[1], {"jobId": child_id})

    def test_zero_faker_changes_fail_the_run(self):
        with patch.object(autotest.SelftestAdapter, "faker_crud", return_value={"ok": True, "changedRows": 0}):
            result = autotest.run_autotest_selftest_case(autotest.selftest_args())
        self.assertFalse(result["ok"])
        self.assertEqual(result["failurePhase"], "FAKER_FAIL")
        self.assertEqual(autotest.run_job_id(result), 100)
