import contextlib
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cc_console import datajob, datasource, raw
from cc_console.cli import build_parser
from cc_console.client import ApiError, ConsoleClient


TRANSFORM_JOB_TYPE_PATH = "/cloudcanal/console/api/v1/inner/constant/transformjobtype"
SUPPORTED_MYSQL_PAIMON = {
    "STRUCT_MIGRATION": {},
    "SYNC": {"FullAmount": "true", "Incremental": "true"},
    "CHECK": {"FullAmount": "true", "Incremental": "true", "NoStructMigration": "true"},
    "MIGRATION": {"FullAmount": "true", "Incremental": "true"},
}


class FakeConsole(ConsoleClient):
    def __init__(self, supported_options=None):
        super().__init__("http://console.test")
        self.supported_options = SUPPORTED_MYSQL_PAIMON if supported_options is None else supported_options
        self.queries = []
        self.prechecks = []
        self.creates = []

    def post_json(self, path, payload):
        if path == datasource.QUERY_DS_PATH:
            source_types = {54: "MySQL", 274: "PolarDbMySQL", 308: "Paimon"}
            return {"code": "1", "data": {"dataSourceType": source_types[payload["dataSourceId"]]}}
        if path == TRANSFORM_JOB_TYPE_PATH:
            self.queries.append(payload)
            source = payload["sourceType"]
            target = payload["targetType"]
            if (source, target) != ("MySQL", "Paimon"):
                return {
                    "code": "0001",
                    "data": None,
                    "msg": f"unsupported source datasource type ({source}) and target datasource type ({target})",
                }
            return {"code": "1", "data": {"source": source, "target": target, "optionType": self.supported_options}}
        if path == datajob.PRECHECK_FINAL_PATH:
            self.prechecks.append(payload)
            return {"code": "1", "data": []}
        if path in (
            datajob.SCHEMA_MAPPING_RULE_PATH,
            datajob.TABLE_MAPPING_RULE_PATH,
            datajob.COLUMN_MAPPING_RULE_PATH,
            datajob.WEBOP_EXTRA_CONFIGS_PATH,
        ):
            return {"code": "1", "data": None}
        raise AssertionError(f"Unexpected POST {path}")

    def post_multipart(self, path, fields):
        if path != datajob.CREATE_JOB_PATH:
            raise AssertionError(f"Unexpected multipart POST {path}")
        self.creates.append(json.loads(fields["dataJobData"].value))
        return {"code": "1", "data": 1}


def create_job(client, source_id, mode, *options):
    args = build_parser().parse_args([
        "create-job",
        "--cluster-id", "1",
        "--spec-id", "15",
        "--source-ds-id", str(source_id),
        "--target-ds-id", "308",
        "--source-schema-json", "[]",
        "--target-schema-json", "[]",
        "--mapping-json", "[]",
        "--source-charset", "utf8",
        "--target-charset", "utf8",
        "--no-struct-migration",
        "--mode", mode,
        *options,
    ])
    with contextlib.redirect_stdout(io.StringIO()):
        return datajob.create_datajob_cmd(args, client)


class JobSupportTest(unittest.TestCase):
    def test_polar_paimon_is_rejected_before_empty_precheck_can_pass(self):
        for mode in ("full-sync", "check"):
            with self.subTest(mode=mode):
                client = FakeConsole()
                with self.assertRaisesRegex(ApiError, "PolarDbMySQL -> Paimon"):
                    create_job(client, 274, mode)
                self.assertEqual([], client.prechecks)
                self.assertEqual([], client.creates)

    def test_mysql_paimon_create_uses_matrix_for_sync_and_check(self):
        for mode, job_type in (("full-sync", "SYNC"), ("check", "CHECK"), ("struct", "STRUCT_MIGRATION")):
            with self.subTest(mode=mode):
                client = FakeConsole()
                self.assertEqual(0, create_job(client, 54, mode))
                self.assertEqual([{"sourceType": "MySQL", "targetType": "Paimon", "cgTableType": "BASE_TABLE"}], client.queries)
                self.assertEqual([job_type], [job["jobType"] for job in client.creates])

    def test_datasource_type_and_payload_overrides_cannot_fake_support(self):
        for source_id, options in (
            (274, ["--source-type", "MySQL"]),
            (54, ["--extra-json", '{"sourceDataSourceId":274}']),
        ):
            with self.subTest(source_id=source_id):
                client = FakeConsole()
                with self.assertRaisesRegex(ApiError, "PolarDbMySQL -> Paimon"):
                    create_job(client, source_id, "full-sync", "--skip-precheck", *options)
                self.assertEqual([], client.creates)

    def test_full_sync_requires_full_load_and_check_requires_check_mode(self):
        for mode, expected in (("full-sync", "does not support a full load"), ("check", "does not offer this task type")):
            with self.subTest(mode=mode):
                client = FakeConsole({"SYNC": {"Incremental": "true"}})
                with self.assertRaisesRegex(ApiError, expected):
                    create_job(client, 54, mode, "--ignore-precheck-fail")
                self.assertEqual([], client.creates)

    def test_raw_job_create_redirects_to_checked_entry_point(self):
        args = build_parser().parse_args([
            "call-api", "--method", "POST", "--path", datajob.CREATE_JOB_PATH, "--multipart",
            "--json-part", 'dataJobData={"sourceDataSourceId":274,"targetDataSourceId":308}',
        ])
        client = FakeConsole()
        with self.assertRaisesRegex(ValueError, "create-job"):
            raw.call_api_cmd(args, client)
        self.assertEqual([], client.creates)


if __name__ == "__main__":
    unittest.main()
