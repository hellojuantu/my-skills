import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ALIAS_CHECK = SCRIPTS / "check_console_field_aliases.py"
GATE_CHECK = SCRIPTS / "check_no_invented_gates.py"


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

