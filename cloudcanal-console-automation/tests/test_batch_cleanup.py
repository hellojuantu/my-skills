import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_auth import run_cli
from cc_console import autotest, datajob, datasource
from cc_console.cli import build_parser
from cc_console.client import ConsoleClient
from cc_console.db_adapters import adapter_for_type
from cc_console.db_adapters.mq import KafkaFamilyAdapter


class BatchCleanupTest(unittest.TestCase):
    def test_create_retains_known_id_or_records_unknown_outcome(self):
        args = SimpleNamespace(dry_run=False, profile="selftest-core", skip_precheck=True, start_timeout_seconds=1)
        adapter = autotest.SelftestAdapter()
        args.source_schema = "cc_auto_source"
        tables = [{"table": name, "targetAutoCreate": True} for name in adapter.profile_tables_for_namespace(None, None)]
        payload = {"sourceSchema": json.dumps([{"db": args.source_schema, "tables": tables}])}
        client = ConsoleClient("https://console.example")
        with patch.object(autotest, "create_job_args"), patch.object(autotest, "build_datajob_payload", return_value=payload):
            with patch.object(client, "post_multipart", side_effect=TimeoutError("creation timed out")):
                result = autotest.create_autotest_job(args, client, "MySQL", "MySQL", adapter)
                self.assertFalse(result["ok"])
                self.assertTrue(result["createOutcomeUnknown"])
            with patch.object(client, "post_multipart", return_value={"code": "1", "data": None}):
                result = autotest.create_autotest_job(args, client, "MySQL", "MySQL", adapter)
                self.assertFalse(result["ok"])
                self.assertTrue(result["createOutcomeUnknown"])
            with patch.object(client, "post_multipart", return_value={"code": "1", "data": 91}):
                with patch.object(autotest, "wait_datajob_create_finished", side_effect=TimeoutError("wait timed out")):
                    result = autotest.create_autotest_job(args, client, "MySQL", "MySQL", adapter)
                self.assertFalse(result["ok"])
                self.assertEqual(result["jobId"], 91)

    def test_cleanup_skips_unknown_or_active_creation_and_checks_the_returned_id(self):
        args = SimpleNamespace(skip_init=False)
        unknown = {"steps": [{"name": "create-job", "result": {"createOutcomeUnknown": True}}]}
        with patch.object(autotest, "cleanup_batch_pair") as cleanup:
            result = autotest.cleanup_after_job_stops(object(), None, args, unknown)
            self.assertIn("creation could not be confirmed", result["skipped"])
            for job, expected in (
                (None, "state could not be confirmed"),
                ({"dataJobId": 92}, "state could not be confirmed"),
                ({"dataJobId": 91, "lifeCycleState": "CREATING", "consoleTaskState": "EXECUTE"}, "creation still in progress"),
            ):
                with self.subTest(job=job), patch.object(autotest, "query_job", return_value=job):
                    result = autotest.cleanup_after_job_stops(object(), 91, args, {"steps": []})
                    self.assertIn(expected, result["skipped"])
            cleanup.assert_not_called()

    def test_cleanup_uses_recorded_target_objects_and_reports_errors(self):
        args = SimpleNamespace(target_ds_id=21, target_type="Kafka", target_password="fixture", target_schema="cc_auto_target")
        objects = ["cc_auto_actual_target"]
        run = {"steps": [{"name": "prepare-target", "result": {"tables": objects}}], "tables": ["cc_auto_source"]}
        adapter = SimpleNamespace(can_cleanup=True, cleanup_dataset=Mock(return_value={"dropped": True}))
        with patch.object(autotest, "query_datasource", return_value={}), patch.object(autotest, "adapter_for_type", return_value=adapter):
            result = autotest.cleanup_batch_pair(object(), args, run)
            self.assertEqual(adapter.cleanup_dataset.call_args.kwargs["tables"], objects)
            self.assertEqual(autotest.cleanup_outcome(result), "performed")
            adapter.cleanup_dataset.side_effect = TimeoutError("cleanup failed")
            result = autotest.cleanup_batch_pair(object(), args, run)
        self.assertEqual(autotest.cleanup_outcome(result), "failed")
        item = {"cleanup": result, "pair": {}, "status": "PASS"}
        report = autotest.render_batch_report({"cleanupAfterRun": True, "pairs": [item]})
        self.assertIn("cleanup: `failed`", report)
        self.assertNotIn("cleanup: `performed`", report)

    def test_cleanup_cli_uses_exact_temporary_object_names(self):
        options = ["autotest-cleanup-dataset", "--base-url", "https://console.example", "--cookie", "fixture",
                   "--data-source-id", "5", "--schema", "cc_auto_target", "--password", "fixture-secret"]
        with patch.object(autotest, "query_datasource", return_value={"dataSourceType": "Kafka"}), patch.object(
            KafkaFamilyAdapter, "cleanup_dataset", return_value={"dropped": True}
        ) as cleanup:
            status, _, errors = run_cli(*options, "--table", "existing-topic")
            self.assertEqual(status, 1, errors)
            cleanup.assert_not_called()
            status, _, errors = run_cli(*options, "--table", "cc_auto_a", "--table", "cc_auto_b")
            self.assertEqual(status, 0, errors)
            self.assertEqual(cleanup.call_args.kwargs["tables"], ["cc_auto_a", "cc_auto_b"])

    def test_generated_kafka_topics_are_used_to_prepare_create_check_and_clean_up(self):
        args = build_parser().parse_args([
            "autotest-run", "--cluster-id", "2", "--spec-id", "15", "--source-ds-id", "10", "--target-ds-id", "20",
            "--source-schema", "cc_auto_source", "--target-schema", "cc_auto_target", "--source-password", "fixture",
            "--target-password", "fixture", "--no-start-after-create", "--no-add-check-child", "--no-collect-stage-logs",
            "--crud-rounds", "0", "--source-charset", "utf8", "--target-charset", "utf8", "--skip-precheck",
        ])
        client = ConsoleClient("https://console.example")
        source = adapter_for_type("MySQL")
        target = adapter_for_type("Kafka")

        def reply(path, payload):
            data = None
            if path == datasource.QUERY_DS_PATH:
                ds_type = "MySQL" if payload["dataSourceId"] == 10 else "Kafka"
                data = {"id": payload["dataSourceId"], "dataSourceType": ds_type}
            elif path == datajob.TRANSFORM_JOB_TYPE_PATH:
                data = {
                    "source": "MySQL", "target": "Kafka",
                    "optionType": {"SYNC": {"FullAmount": "true", "Incremental": "true"}},
                }
            elif path == datajob.QUERY_JOB_PATH:
                data = {"dataJobId": 91, "lifeCycleState": "CREATED", "consoleTaskState": "SUCCESS"}
            return {"code": "1", "data": data}

        def source_columns(*params):
            for table in params[-2]:
                table["sourceColumns"] = [{"column": "id"}]

        with patch.object(client, "post_json", side_effect=reply), patch.object(
            client, "post_multipart", return_value={"code": "1", "data": 91}
        ) as submit, patch.object(datajob, "enrich_source_columns", side_effect=source_columns), patch.object(
            autotest, "wait_full_complete", return_value={}
        ), patch.object(source, "init_source_dataset", return_value={}), patch.object(
            source, "cleanup_dataset", return_value={"dropped": True}
        ), patch.object(source, "table_snapshot", return_value={"exists": True, "rows": 4}), patch.object(
            target, "table_snapshot", return_value={"exists": True, "rows": 4}
        ) as read_topics, patch.object(target, "_create_object") as create_topics, patch.object(target, "_delete_object") as delete_topics:
            run = autotest.run_autotest_pair(args, client)
            self.assertTrue(run["ok"], run.get("error"))
            prepared = [call.args[2] for call in create_topics.call_args_list]
            self.assertTrue(prepared)
            self.assertTrue(all(name.startswith("cc_auto_target_") for name in prepared))
            self.assertTrue(set(prepared).isdisjoint(run["tables"]))
            fields = submit.call_args.args[1]
            payload = json.loads(fields["dataJobData"].value)
            self.assertEqual([topic["topic"] for topic in json.loads(payload["targetSchema"])], prepared)
            self.assertEqual([call.args[3] for call in read_topics.call_args_list], prepared)
            cleaned = autotest.cleanup_after_job_stops(client, 91, args, run)
            self.assertEqual(autotest.cleanup_outcome(cleaned), "performed")
            self.assertEqual([call.args[2] for call in delete_topics.call_args_list], prepared + prepared)

    def test_cleanup_skipped_for_active_job_offers_no_dataset_delete_command(self):
        item = {
            "jobId": 91, "pair": {"targetDataSourceId": 20}, "targetSchema": "cc_auto_target",
            "datasetTables": {"target": ["cc_auto_topic"]}, "cleanup": {"skipped": "job still running"},
        }
        commands = autotest.followup_commands(item)
        self.assertTrue(any("query-job" in command for command in commands))
        self.assertFalse(any("autotest-cleanup-dataset" in command for command in commands))

    def test_long_run_names_keep_source_target_and_pair_names_distinct(self):
        args = build_parser().parse_args(["autotest-batch-run", "--password", "fixture"])
        pair = {"sourceDataSourceId": 10, "targetDataSourceId": 20, "sourceType": "MySQL", "targetType": "Kafka"}
        run_id = "fixture_" + "x" * 80
        first = autotest.batch_pair_args(args, pair, 1, run_id, {})
        second = autotest.batch_pair_args(args, pair, 2, run_id, {})
        names = {first.source_schema, first.target_schema, second.source_schema, second.target_schema}
        self.assertEqual(len(names), 4)
        self.assertTrue(all(name.startswith("cc_auto_") and len(name) <= 63 for name in names))

    def test_cleanup_failure_makes_batch_cli_fail_without_erasing_pair_pass(self):
        matrix = {"pairs": [{"sourceDataSourceId": 10, "targetDataSourceId": 20, "fullDataVerificationReady": True}]}
        for concurrency in (1, 2):
            with self.subTest(concurrency=concurrency), TemporaryDirectory() as output, patch.object(
                autotest, "run_batch_pair", return_value={"status": "PASS", "cleanup": {"target": {"error": "permission denied"}}, "pair": matrix["pairs"][0]}
            ):
                status, stdout, stderr = run_cli(
                    "autotest-batch-run", "--base-url", "https://console.example", "--cookie", "fixture", "--matrix-json", json.dumps(matrix),
                    "--cleanup-after-run", "--output-dir", output, "--max-concurrency", str(concurrency),
                )
                self.assertEqual(status, 2, stderr)
                self.assertFalse(json.loads(stdout)["ok"])
                report = json.loads((Path(output) / "batch-result.json").read_text())
                self.assertEqual(report["pairs"][0]["status"], "PASS")
                self.assertEqual(report["pairs"][0]["cleanup"]["target"]["error"], "permission denied")
