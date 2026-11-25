from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "slot_claim.py"


def configured_mini_host():
    path = SCRIPT.parents[1] / "skills" / "cc-setup" / "mini.env"
    for raw in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = raw.strip().partition("=")
        if sep and key == "MINI_HOSTNAME":
            return value.strip()
    return ""


class SlotClaimTest(unittest.TestCase):
    def setUp(self):
        here = socket.gethostname().split(".", 1)[0]
        if here != configured_mini_host():
            self.skipTest("claim behavior runs on the machine named in mini.env")
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "private").mkdir()
        (self.root / "slots.json").write_text(json.dumps({
            "01": {"consolePort": 8111}, "02": {"consolePort": 8112},
        }), encoding="utf-8")

    def invoke(self, *args):
        env = os.environ.copy()
        env.pop("CC_MINI_HOSTNAME", None)
        return subprocess.run(
            [sys.executable, SCRIPT, "--on-mini", "--root", self.root, *args],
            capture_output=True, text=True, timeout=15, env=env,
        )

    def payload(self, result, *, ok=True):
        self.assertEqual(result.returncode == 0, ok, result.stderr or result.stdout)
        body = json.loads(result.stdout)
        self.assertIs(body["ok"], ok)
        return body

    def acquire(self, session="chat-id", slot="01"):
        return self.invoke(
            "acquire", slot, "--access", "write", "--machine", "Pro", "--agent", "Codex",
            "--hostname", "pro.local", "--run-id", "release-1", "--branch", "test",
            "--session-id", session, "--session-title", "review chat",
            "--session-url", "codex://test/fixture",
        )

    def slots(self):
        rows = self.payload(self.invoke("status"))["slots"]
        return {row["slot"]: row for row in rows}

    def release(self, claim_id, reason):
        return self.invoke("release", "01", "--claim-id", claim_id, "--reason", reason)

    def test_claim_updates_handoff_and_archives_on_release(self):
        initial = self.slots()
        self.assertEqual(initial["01"]["consolePort"], 8111)
        self.assertIsNone(initial["01"]["claim"])
        claim = self.payload(self.acquire())["claim"]
        for field, value in {
            "machine": "Pro", "hostname": "pro.local", "agent": "Codex",
            "runId": "release-1", "branch": "test", "access": "write", "sessionId": "chat-id",
            "sessionTitle": "review chat", "sessionUrl": "codex://test/fixture",
        }.items():
            self.assertEqual(claim[field], value, field)
        for field in ("claimedAt", "updatedAt"):
            self.assertIsNotNone(datetime.fromisoformat(claim[field].replace("Z", "+00:00")).tzinfo)
        claim_id = claim["claimId"]
        self.assertTrue(claim_id)
        updated = self.payload(self.invoke(
            "update", "01", "--claim-id", claim_id, "--phase", "awaiting-handoff",
            "--job-id", "123", "--note", "waiting",
        ))["claim"]
        self.assertEqual(updated["claimId"], claim_id)
        self.assertEqual(updated["phase"], "awaiting-handoff")
        self.assertEqual(updated["jobIds"], [123])
        self.assertEqual(updated["note"], "waiting")
        self.assertEqual(self.slots()["01"]["claim"]["phase"], "awaiting-handoff")
        self.assertIsNone(self.slots()["02"]["claim"])
        archive = self.payload(self.release(claim_id, "completed"))["archivePath"]
        self.assertTrue((self.root / archive).exists(), archive)
        self.assertIsNone(self.slots()["01"]["claim"])

    def test_stale_claim_id_cannot_change_the_next_claim(self):
        old_id = self.payload(self.acquire())["claim"]["claimId"]
        self.payload(self.release(old_id, "completed"))
        replacement = self.payload(self.acquire("another-chat"))["claim"]
        self.assertNotEqual(old_id, replacement["claimId"])
        self.payload(self.invoke("update", "01", "--claim-id", old_id, "--note", "stale"), ok=False)
        self.payload(self.release(old_id, "completed"), ok=False)
        current = self.slots()["01"]["claim"]
        self.assertEqual(current["claimId"], replacement["claimId"])
        self.assertNotEqual(current.get("note"), "stale")

    def test_status_cannot_combine_claims_from_before_and_after_a_handoff(self):
        claim_id = self.payload(self.acquire())["claim"]["claimId"]
        spec = importlib.util.spec_from_file_location("slot_claim", SCRIPT)
        claims = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(claims)
        real_lock = claims.slot_lock

        @contextmanager
        def handoff_after_unlock(private, slot, exclusive=True):
            with real_lock(private, slot, exclusive=exclusive):
                yield
            if slot == "01" and not exclusive:
                self.payload(self.release(claim_id, "completed"))
                self.payload(self.acquire(slot="02"))

        registered = json.loads((self.root / "slots.json").read_text(encoding="utf-8"))
        with patch.object(claims, "slot_lock", handoff_after_unlock):
            snapshot = claims.status(self.root / "private", registered)
        self.assertFalse(snapshot["allRegisteredClaimed"])
        first, second = snapshot["slots"]
        self.assertEqual(first["claim"]["claimId"], claim_id)
        self.assertIsNone(second["claim"])
        after = self.slots()
        self.assertIsNone(after["01"]["claim"])
        self.assertIsNotNone(after["02"]["claim"])

    def test_recorded_legacy_owner_text_stays_readable(self):
        samples = {
            "01": (
                "executor=codex-binlog-dev-revert\n"
                "branch=fix/ob-typed-paimon-compat\n"
                "release=mysql-binlog-dev-revert-20261123\n"
                "2026-11-23T13:14:53Z\n"
            ),
            "02": (
                "agent=mini_preflight\n"
                "branch=fix/ob-typed-paimon-compat\n"
                "case=set-writer-1124055024\n"
                "claimedAt=2026-11-24T05:50:24Z\n"
            ),
        }
        for slot, text in samples.items():
            claim_dir = self.root / "private" / f".claim-{slot}"
            claim_dir.mkdir()
            (claim_dir / "owner").write_text(text, encoding="utf-8")
        rows = self.slots()
        first = rows["01"]["claim"]
        self.assertTrue(first["legacy"])
        self.assertEqual(first["agent"], "codex-binlog-dev-revert")
        self.assertEqual(first["runId"], "mysql-binlog-dev-revert-20261123")
        self.assertEqual(first["branch"], "fix/ob-typed-paimon-compat")
        self.assertEqual(first["claimedAt"], "2026-11-23T13:14:53Z")
        self.assertIsNone(first["sessionId"])
        self.assertIsNone(first["machine"])
        second = rows["02"]["claim"]
        self.assertEqual(second["agent"], "mini_preflight")
        self.assertEqual(second["runId"], "set-writer-1124055024")
        self.assertEqual(second["claimedAt"], "2026-11-24T05:50:24Z")
        self.assertIsNone(second["sessionId"])
        self.assertIsNone(second["sessionUrl"])

    def test_old_legacy_claim_requires_confirmed_release(self):
        claim_dir = self.root / "private" / ".claim-01"
        claim_dir.mkdir()
        owner = claim_dir / "owner"
        owner.write_text(
            "agent=Codex\nbranch=test\nclaimed_at=2001-01-01T00:00:00Z\n", encoding="utf-8",
        )
        for path in (owner, claim_dir):
            os.utime(path, (978307200, 978307200))
        claim = self.slots()["01"]["claim"]
        self.assertTrue(claim["legacy"])
        self.assertIsNone(claim["sessionId"])
        self.payload(self.acquire(), ok=False)
        self.payload(self.release(claim["claimId"], "confirmed-ended"))
        self.assertIsNone(self.slots()["01"]["claim"])

    def test_concurrent_acquisitions_have_one_owner(self):
        barrier = Barrier(2)

        def contender(session):
            barrier.wait(timeout=10)
            return self.acquire(session)

        sessions = ("chat-a", "chat-b")
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(contender, sessions))
        winners = [session for session, result in zip(sessions, outcomes) if result.returncode == 0]
        self.assertEqual(len(winners), 1, [result.stderr or result.stdout for result in outcomes])
        self.assertEqual(self.slots()["01"]["claim"]["sessionId"], winners[0])


class SlotClaimHostTest(unittest.TestCase):
    def test_spoofed_hostname_cannot_override_mini_env(self):
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        private = Path(root.name) / "private"
        private.mkdir()
        (Path(root.name) / "slots.json").write_text('{"01": {"consolePort": 8111}}', encoding="utf-8")
        env = os.environ.copy()
        env["CC_MINI_HOSTNAME"] = "not-the-mini"
        result = subprocess.run(
            [sys.executable, SCRIPT, "--on-mini", "--root", root.name, "status"],
            capture_output=True, text=True, timeout=15, env=env,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("mini.env", result.stdout)


if __name__ == "__main__":
    unittest.main()
