import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ALIAS_CHECK = SCRIPTS / "check_console_field_aliases.py"
GATE_CHECK = SCRIPTS / "check_no_invented_gates.py"
HOST_CHECK = SCRIPTS / "check_mini_host.py"


def run_check(script, *paths):
    return subprocess.run(
        [sys.executable, str(script), *[str(path) for path in paths]],
        capture_output=True,
        text=True,
    )


class ConsoleFieldAliasCheck(unittest.TestCase):
    def test_current_scripts_use_one_field_name(self):
        result = run_check(ALIAS_CHECK, SCRIPTS)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_old_fsm_id_fallback_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "datajob.py"
            sample.write_text(
                "def fsm_id_from_job(job):\n"
                "    for key in (\"fsmId\", \"fsmID\", \"fsm_id\"):\n"
                "        if job.get(key):\n"
                "            return job.get(key)\n",
                encoding="utf-8",
            )
            result = run_check(ALIAS_CHECK, sample)
        self.assertEqual(1, result.returncode)
        self.assertIn("fsmID", result.stderr)
        self.assertIn("fsmID, fsmId, fsm_id", result.stderr)


class InventedGateCheck(unittest.TestCase):
    def test_current_commands_have_no_invented_gate(self):
        result = run_check(GATE_CHECK)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_old_release_result_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "autotest.py"
            sample.write_text(
                'run["failurePhase"] = "RELEASE_STAGES_NOT_RUN"\n',
                encoding="utf-8",
            )
            result = run_check(GATE_CHECK, sample)
        self.assertEqual(1, result.returncode)
        self.assertIn("RELEASE_STAGES_NOT_RUN", result.stderr)


class MiniHostCheck(unittest.TestCase):
    def test_current_scripts_read_configured_names(self):
        result = run_check(HOST_CHECK)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_old_hardcoded_mini_url_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "auth.py"
            sample.write_text(
                'slot = re.fullmatch(r"http://mini:([0-9]{1,5})", origin)\n',
                encoding="utf-8",
            )
            result = run_check(HOST_CHECK, sample)
        self.assertEqual(1, result.returncode)
        self.assertIn("Mini host is hardcoded", result.stderr)


CLAIM_CHECK = Path(__file__).resolve().parents[2] / "cloudcanal-dev-test" / "skills" / "verify-slot-claim" / "scripts" / "code_matches_model.py"
CLAIM_SOURCE = Path(__file__).resolve().parents[2] / "cloudcanal-dev-test" / "scripts" / "slot_claim.py"


class ClaimLockCheck(unittest.TestCase):
    def test_current_change_claim_holds_the_write_lock(self):
        result = run_check(CLAIM_CHECK, CLAIM_SOURCE)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_change_claim_outside_the_lock_fails(self):
        text = CLAIM_SOURCE.read_text(encoding="utf-8")
        text = text.replace("    with slot_lock(private, slot, exclusive=True):\n", "    if True:\n", 1)
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory) / "slot_claim.py"
            sample.write_text(text, encoding="utf-8")
            result = run_check(CLAIM_CHECK, sample)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("change_claim does not hold the write lock", result.stderr)

