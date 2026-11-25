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
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "mini.env"
        path.write_text("MINI_HOSTNAME=lab-box\nMINI_SSH_HOST=Mini\nMINI_TAILSCALE_NAME=Box.Lab.Test.\n")
        names = auth.mini_name_module()
        for fixture in (
            patch.object(auth, "mini_name_module", return_value=names),
            patch.object(names, "mini_env_path", return_value=path),
            patch.dict(os.environ, {f"CC_{key}": "" for key in names.MINI_NAME_KEYS}),
        ):
            fixture.start()
            self.addCleanup(fixture.stop)

    def test_only_configured_hosts_require_mini_session(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "session"
            for host in ("LAB-BOX", "mini", "box.lab.test.", "mini.unrelated.test"):
                origin = f"http://{host}:8111"
                args = cli.build_parser().parse_args(["clusters", "--base-url", origin, "--cookie-file", str(cookie)])
                cookie.write_text("jwt_token=example\n")
                with self.subTest(origin=origin):
                    if host == "mini.unrelated.test":
                        self.assertEqual(auth.read_cookie(args), "jwt_token=example")
                        continue
                    with self.assertRaisesRegex(auth.ApiError, "Mini needs an existing session"):
                        auth.read_cookie(args)
                    cookie.write_text(f"# origin={origin}\njwt_token=example\n")
                    self.assertEqual(auth.read_cookie(args), "jwt_token=example")
                    cookie.write_text(f"# origin=http://{host}:8112\njwt_token=example\n")
                    with self.assertRaisesRegex(auth.ApiError, "Session file is for"):
                        auth.read_cookie(args)

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

    def test_missing_mini_session_file_ignores_global_cookie(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CC_COOKIE": "global-jwt"}):
            status, _, errors = run_cli(
                "clusters", "--base-url", "http://mini:8113", "--cookie-file", str(Path(directory) / "missing"),
            )
            self.assertEqual(1, status)
            self.assertIn("login --base-url http://mini:8113 --save-cookie", errors)
            self.assertNotIn("global-jwt", errors)

    def test_mini_only_sends_cookie_from_a_matching_origin_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CC_COOKIE": "env-cookie"}):
            session = Path(directory) / "session"
            for host in ("mini", "box.lab.test"):
                origin = f"http://{host}:8111"
                args = ["clusters", "--base-url", origin]
                explicit = ["--cookie", "argument-cookie", "--header", "cOoKiE=header-cookie"]
                file_args = ["--cookie-file", str(session)]
                with self.subTest(host=host), patch.object(auth.ConsoleClient, "send", autospec=True) as send:
                    session.write_text(f"# origin=http://{host}:8112\njwt_token=file-cookie\n")
                    for options in ([], explicit, [*explicit, *file_args]):
                        status, _, errors = run_cli(*args, *options)
                        self.assertEqual(1, status, errors)
                    send.assert_not_called()

                    session.write_text(f"# origin={origin}\njwt_token=file-cookie\n")
                    send.return_value = {"code": "1", "data": []}
                    status, _, errors = run_cli(*args, *explicit, *file_args)
                    self.assertEqual(0, status, errors)
                    self.assertEqual("jwt_token=file-cookie", send.call_args.args[1].get_header("Cookie"))

    def test_external_console_keeps_cookie_precedence(self):
        args = ["clusters", "--base-url", "https://console.example"]
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"CC_COOKIE": "env-cookie"}):
            session = Path(directory) / "session"
            session.write_text("file-cookie\n")
            file_args = ["--cookie-file", str(session)]
            cases = [
                ([], "env-cookie"),
                (file_args, "file-cookie"),
                ([*file_args, "--cookie", "argument-cookie"], "argument-cookie"),
                ([*file_args, "--cookie", "argument-cookie", "--header", "Cookie=header-cookie"], "header-cookie"),
            ]
            for options, expected in cases:
                with self.subTest(options=options), patch.object(auth.ConsoleClient, "send", autospec=True) as send:
                    send.return_value = {"code": "1", "data": []}
                    status, _, errors = run_cli(*args, *options)
                    self.assertEqual(0, status, errors)
                    self.assertEqual(expected, send.call_args.args[1].get_header("Cookie"))

    def test_session_file_rejects_a_different_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie = Path(directory) / "session"
            cookie.write_text("# origin=http://mini:8113\njwt_token=example-token\n")
            args = cli.build_parser().parse_args([
                "clusters", "--base-url", "http://mini:8111", "--cookie-file", str(cookie),
            ])
            with self.assertRaises(auth.ApiError) as caught:
                auth.read_cookie(args)
            self.assertIn("http://mini:8113", str(caught.exception))

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
            cookie.write_text("# origin=http://mini:8111\njwt_token=example\n")
            args = cli.build_parser().parse_args(["clusters", "--base-url", "http://mini:8111", "--cookie-file", str(cookie)])
            with patch.object(auth, "prompt_line") as prompt:
                self.assertEqual("jwt_token=example", auth.client_from_args(args).cookie)
                prompt.assert_not_called()
            cookie.write_text("jwt_token=example\n")
            with self.assertRaises(auth.ApiError) as caught:
                auth.read_cookie(args)
            self.assertIn("login --base-url http://mini:8111 --save-cookie", str(caught.exception))

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
                    self.assertEqual("# origin=http://mini:8113\njwt_token=example-token\n", cookie.read_text())
                    self.assertEqual(0o600, stat.S_IMODE(cookie.stat().st_mode))
