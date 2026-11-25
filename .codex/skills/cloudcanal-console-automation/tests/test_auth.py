import contextlib
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cc_console import auth, cli


def run_cli(*args):
    output = io.StringIO()
    errors = io.StringIO()
    with patch.object(sys, "argv", ["create_datajob.py", *args]):
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = cli.main()
    return status, output.getvalue(), errors.getvalue()


class ConsoleAuthTest(unittest.TestCase):
    def test_mini_missing_session_stops_before_prompt_or_request(self):
        for port in (8111, 8112, 8113):
            origin = f"http://mini:{port}"
            with self.subTest(origin=origin), patch.dict(os.environ, {"CC_COOKIE": ""}):
                with patch.object(auth, "prompt_line") as prompt, patch.object(auth, "ConsoleClient") as client:
                    status, _, errors = run_cli("clusters", "--base-url", origin)
                prompt.assert_not_called()
                client.assert_not_called()
                self.assertEqual(1, status)
                self.assertIn(f"login --base-url {origin} --save-cookie", errors)

    def test_missing_mini_session_file_directs_user_to_login(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CC_COOKIE": ""}):
            status, _, errors = run_cli(
                "clusters", "--base-url", "http://mini:8113", "--cookie-file", str(Path(directory) / "missing"),
            )
            self.assertEqual(1, status)
            self.assertIn("login --base-url http://mini:8113 --save-cookie", errors)

    def test_supplied_mini_session_and_external_interactive_prompt_still_work(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "session"
            cookie.write_text("jwt_token=example\n")
            args = cli.build_parser().parse_args(["clusters", "--base-url", "http://mini:8111", "--cookie-file", str(cookie)])
            with patch.object(auth, "prompt_line") as prompt:
                self.assertEqual("jwt_token=example", auth.client_from_args(args).cookie)
                prompt.assert_not_called()

        args = cli.build_parser().parse_args(["clusters", "--base-url", "https://console.example"])
        with patch.dict(os.environ, {"CC_COOKIE": ""}), patch.object(auth, "prompt_line", return_value="existing") as prompt:
            self.assertEqual("existing", auth.client_from_args(args).cookie)
            prompt.assert_called_once()

    def test_login_hands_identity_challenges_to_user_without_returning_session(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "session"
            for challenge in ("needMfa", "needMore"):
                with self.subTest(challenge=challenge):
                    response = {"code": "1", "data": {"success": True, challenge: True, "token": "example-token"}}
                    with patch.object(auth.ConsoleClient, "post_json", return_value=response):
                        status, output, errors = run_cli(
                            "login", "--base-url", "http://mini:8111", "--account", "example",
                            "--password", "example", "--password-encrypted", "--save-cookie", str(cookie),
                        )
                    self.assertEqual(1, status)
                    self.assertIn("ask the user", errors)
                    self.assertNotIn("example-token", errors + output)
                    self.assertFalse(cookie.exists())

    def test_login_saves_new_and_existing_sessions_with_private_permissions(self):
        response = {"code": "1", "data": {"success": True, "token": "example-token"}}
        with tempfile.TemporaryDirectory() as directory, patch.object(auth.ConsoleClient, "post_json", return_value=response):
            cookie = Path(directory) / "session"
            for existing in (False, True):
                with self.subTest(existing=existing):
                    if existing:
                        cookie.write_text("old session\n")
                        cookie.chmod(0o644)
                    status, output, errors = run_cli(
                        "login", "--base-url", "http://mini:8113", "--account", "example",
                        "--password", "example", "--password-encrypted", "--save-cookie", str(cookie),
                    )
                    self.assertEqual(0, status, errors)
                    self.assertNotIn("example-token", output + errors)
                    self.assertEqual("jwt_token=example-token\n", cookie.read_text())
                    self.assertEqual(0o600, stat.S_IMODE(cookie.stat().st_mode))
