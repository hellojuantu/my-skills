import os
from pathlib import Path
import selectors
import shlex
import shutil
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
AUTH_MESSAGE = (
    "# Tailscale SSH requires an additional check.\n"
    "# To authenticate, visit: https://login.tailscale.com/a/fixture-ssh-check\n"
)


class MiniSshAuthTest(unittest.TestCase):
    def invoke(self, entrypoint, stderr, stdout="", status=255):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("run_mini_test.py", "run-mini-test.sh", "mini_names.py", "slot_claim.py", "ssh_auth.py"):
                source = SCRIPTS / name
                if source.exists():
                    shutil.copy2(source, scripts / name)
            config = root / "skills" / "cc-setup" / "mini.env"
            config.parent.mkdir(parents=True)
            config.write_text("MINI_HOSTNAME=fixture-mini\nMINI_SSH_HOST=fixture-alias\n"
                              "MINI_TAILSCALE_NAME=fixture.private.test\nMINI_SSH_USER=fixture\n")
            ssh = root / "ssh"
            ssh.write_text("#!/bin/sh\n"
                           f"printf %s {shlex.quote(stderr)} >&2\n"
                           f"printf %s {shlex.quote(stdout)}\n"
                           f"exit {status}\n")
            ssh.chmod(0o755)
            args = ["--", "true"] if entrypoint == "run_mini_test.py" else ["status"]
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"])
            return subprocess.run([sys.executable, scripts / entrypoint, *args],
                                  capture_output=True, text=True, timeout=10, env=env)

    def test_both_ssh_entrypoints_choose_existing_google_before_handoff(self):
        for entrypoint in ("run_mini_test.py", "slot_claim.py"):
            with self.subTest(entrypoint=entrypoint):
                result = self.invoke(entrypoint, AUTH_MESSAGE)
                self.assertEqual(result.returncode, 255, result.stderr)
                self.assertIn("CUA", result.stderr)
                self.assertIn("Google Chrome", result.stderr)
                self.assertIn("select an already signed-in Google account", result.stderr)
                self.assertIn("Authorization successful", result.stderr)
                self.assertIn("A Google account chooser is an agent action", result.stderr)
                self.assertIn("password, MFA, CAPTCHA", result.stderr)
                self.assertIn("retry the original SSH command", result.stderr)
                self.assertNotIn("Check the SSH connection", result.stderr)
                self.assertNotIn("Mini did not return a claim result", result.stderr)

    def test_connection_failure_is_not_reclassified_as_browser_auth(self):
        message = "ssh: connect to host fixture.private.test port 22: Connection refused\n"
        for entrypoint in ("run_mini_test.py", "slot_claim.py"):
            with self.subTest(entrypoint=entrypoint):
                result = self.invoke(entrypoint, message)
                self.assertEqual(result.returncode, 255)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Google Chrome", result.stderr)

    def test_claim_reply_stays_json_on_stdout(self):
        reply = '{"ok": true, "slots": []}\n'
        result = self.invoke("slot_claim.py", "", reply, 0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, reply)
        self.assertEqual(result.stderr, "")

    def test_auth_hint_is_emitted_while_ssh_is_still_waiting(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            release = root / "release"
            ssh = root / "ssh"
            ssh.write_text("#!/bin/sh\n"
                           f"printf %s {shlex.quote(AUTH_MESSAGE)} >&2\n"
                           f"while [ ! -f {shlex.quote(str(release))} ]; do sleep 0.1; done\n"
                           "exit 255\n")
            ssh.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"])
            for entrypoint, args in (("run_mini_test.py", ["--", "true"]), ("slot_claim.py", ["status"])):
                with self.subTest(entrypoint=entrypoint):
                    config = root / "skills" / "cc-setup" / "mini.env"
                    config.parent.mkdir(parents=True, exist_ok=True)
                    config.write_text("MINI_HOSTNAME=fixture-mini\nMINI_SSH_HOST=fixture-alias\n"
                                      "MINI_TAILSCALE_NAME=fixture.private.test\nMINI_SSH_USER=fixture\n")
                    scripts = root / "scripts"
                    scripts.mkdir(exist_ok=True)
                    for name in (entrypoint, "run-mini-test.sh", "mini_names.py", "ssh_auth.py"):
                        shutil.copy2(SCRIPTS / name, scripts / name)
                    release.unlink(missing_ok=True)
                    with subprocess.Popen([sys.executable, scripts / entrypoint, *args], env=env,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                        try:
                            deadline = time.monotonic() + 5
                            received = b""
                            with selectors.DefaultSelector() as ready:
                                ready.register(process.stderr, selectors.EVENT_READ)
                                while b"select an already signed-in Google account" not in received:
                                    events = ready.select(max(0, deadline - time.monotonic()))
                                    self.assertTrue(events, "SSH is waiting without browser guidance")
                                    chunk = os.read(process.stderr.fileno(), 4096)
                                    self.assertTrue(chunk, "SSH exited without browser guidance")
                                    received += chunk
                            self.assertIsNone(process.poll(), "Guidance waited for SSH to finish")
                        finally:
                            release.touch()
                            process.communicate(timeout=10)

    def test_claim_script_sent_to_mini_needs_no_browser_helper(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "private").mkdir()
            (root / "slots.json").write_text("{}")
            env = dict(os.environ, CC_MINI_HOSTNAME=socket.gethostname().split(".", 1)[0])
            result = subprocess.run([sys.executable, "-", "--on-mini", "--root", root, "status"],
                                    input=(SCRIPTS / "slot_claim.py").read_text(), capture_output=True,
                                    text=True, timeout=10, cwd=root, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"ok": true', result.stdout)

    def test_reporter_handles_direct_ssh_and_ignores_unrelated_urls(self):
        result = subprocess.run([sys.executable, SCRIPTS / "ssh_auth.py"], input=AUTH_MESSAGE,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Google Chrome", result.stderr)
        result = subprocess.run([sys.executable, SCRIPTS / "ssh_auth.py", "https://unrelated.test/a/check"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Google Chrome", result.stderr)


if __name__ == "__main__":
    unittest.main()
