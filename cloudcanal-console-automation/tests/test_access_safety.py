import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_auth import run_cli
from cc_console import auth
from cc_console.client import ConsoleClient


class ConsoleAccessSafetyTest(unittest.TestCase):
    def test_doctor_sends_only_matching_session_cookie(self):
        origin = "https://console.example"
        token = "jwt_token=fixture-only"
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CC_BASE_URL": origin}):
            session = Path(directory) / "session"
            args = ["doctor", "--check-api", "--cookie-file", str(session)]
            with patch.object(ConsoleClient, "send", autospec=True, return_value={"code": "1", "data": {"id": 7}}) as send:
                session.write_text(f"# origin={origin}\n{token}\n")
                status, output, errors = run_cli(*args)
                self.assertEqual(0, status, errors)
                self.assertEqual({"ok": True, "defaultCluster": {"id": 7}}, json.loads(output)["console"]["apiCheck"])
                self.assertEqual(token, send.call_args.args[1].get_header("Cookie"))
                self.assertNotIn(token, output + errors)

                send.reset_mock()
                session.write_text(f"# origin={origin}:8112\n{token}\n")
                status, output, errors = run_cli(*args)
                self.assertEqual(0, status, errors)
                result = json.loads(output)["console"]["apiCheck"]
                self.assertFalse(result["ok"])
                self.assertIn("Session file is for", result["reason"])
                self.assertNotIn(token, output + errors)
                send.assert_not_called()

    def test_doctor_reports_missing_or_invalid_credentials_without_prompt_or_secret(self):
        args = ["doctor", "--check-api", "--base-url", "https://console.example"]
        with patch.dict(os.environ, {"CC_COOKIE": ""}), patch.object(auth, "prompt_line") as prompt:
            status, output, errors = run_cli(*args)
            self.assertEqual(0, status, errors)
            self.assertFalse(json.loads(output)["console"]["apiCheck"]["ok"])
            prompt.assert_not_called()

        token = "jwt_token=fixture-only"
        with patch.object(ConsoleClient, "send", side_effect=ValueError("Invalid header value: " + token)):
            status, output, errors = run_cli(*args, "--cookie", token + "\ninvalid")
        self.assertEqual(0, status, errors)
        self.assertFalse(json.loads(output)["console"]["apiCheck"]["ok"])
        self.assertNotIn(token, output + errors)

    def test_raw_output_is_required_before_dispatch_and_optional_for_preview(self):
        path = "/cloudcanal/console/example"
        with tempfile.TemporaryDirectory() as directory:
            api = Path(directory) / "src/services/http/api"
            api.mkdir(parents=True)
            (api / "example.js").write_text(f"{{example: '{path}'}}")
            commands = [
                ["call-api", "--path", path, "--method", "GET"],
                ["call-api", "--path", path, "--method", "POST"],
                ["call-service", "--service", "example", "--frontend-dir", directory, "--multipart"],
            ]
            for command in commands:
                with self.subTest(command=command), patch.object(ConsoleClient, "send_raw") as send:
                    args = [*command, "--base-url", "https://console.example", "--cookie", "fixture", "--response", "raw"]
                    status, _, errors = run_cli(*args)
                    self.assertEqual(1, status)
                    self.assertIn("--response raw requires --output", errors)
                    status, output, errors = run_cli(*args, "--dry-run")
                    self.assertEqual(0, status, errors)
                    self.assertEqual(path, json.loads(output)["path"])
                    send.assert_not_called()

                    send.return_value = (200, {}, b"\x00\xff")
                    target = Path(directory) / "response.bin"
                    status, _, errors = run_cli(*args, "--output", str(target))
                    self.assertEqual(0, status, errors)
                    self.assertEqual(b"\x00\xff", target.read_bytes())
                    send.assert_called_once()

    def test_datasource_preview_masks_kv_secrets_and_strict_create_validates_final_value(self):
        args = [
            "create", "--base-url", "https://console.example", "--cookie", "fixture",
            "--type", "mysql", "--host", "db.example", "--user", "tester", "--non-interactive", "--strict-required",
        ]
        defs = [
            {"configName": "apiToken", "valueRequire": True, "defaultValue": "default-token"},
            {"configName": "timeout", "defaultValue": "30"},
            {"configName": "region", "defaultValue": "west"},
        ]
        with patch.object(ConsoleClient, "post_json", return_value={"code": "1", "data": defs}):
            with patch.object(ConsoleClient, "post_multipart", return_value={"code": "1", "data": 7}) as create:
                status, _, errors = run_cli(*args, "--set", "apiToken=")
                self.assertEqual(1, status)
                self.assertIn("missing required extra config: apiToken", errors)

                overrides = ["--set", "apiToken=fixture-only", "--set", "region="]
                status, output, errors = run_cli(*args, *overrides, "--dry-run")
                self.assertEqual(0, status, errors)
                self.assertNotIn("fixture-only", output + errors)
                preview = json.loads(output.split("Dry run payload:\n")[1])["dsKvConfigs"]
                self.assertEqual(["***", "30", ""], [row["configValue"] for row in preview])
                create.assert_not_called()

                status, _, errors = run_cli(*args, *overrides)
                self.assertEqual(0, status, errors)
                actual = json.loads(create.call_args.args[1]["DataSourceAddData"])["dsKvConfigs"]
                self.assertEqual(["fixture-only", "30", ""], [row["configValue"] for row in actual])
