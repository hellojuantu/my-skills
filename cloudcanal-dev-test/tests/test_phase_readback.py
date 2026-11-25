import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECK = Path(__file__).resolve().parents[1] / "scripts" / "check_console_jobs.py"
HEADER = "id\tphase\tsource_utc\ttarget_utc\tdelta_seconds\tdatetime_equal"
# Native MySQL readback from Mini job 14 after removing timestampInstant.
FIRST = "2026-11-01 08:30:00.123456"
SECOND = "2026-11-01 09:30:00.123456"
FOLD_ROWS = (
    ("3", "full-first-01-30", FIRST, SECOND, "3600.000000", "1"),
    ("4", "full-second-01-30", SECOND, SECOND, "0.000000", "1"),
    ("13", "cdc-first-01-30", FIRST, FIRST, "0.000000", "1"),
    ("14", "cdc-second-01-30", SECOND, FIRST, "-3600.000000", "1"),
)


class PhaseReadbackTest(unittest.TestCase):
    def run_check(self, rows, expect="correct", header=HEADER):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "compare.tsv"
            report.write_text(header + "\n" + "\n".join("\t".join(row) for row in rows) + "\n", encoding="utf-8")
            return subprocess.run([sys.executable, str(CHECK), "phase-readback", str(report), "--expect", expect],
                                  capture_output=True, text=True)

    def test_historical_fold_fails_both_claims(self):
        result = self.run_check(FOLD_ROWS)
        self.assertEqual(1, result.returncode)
        self.assertIn("full-first-01-30", result.stderr)
        self.assertIn("cdc-second-01-30", result.stderr)

        result = self.run_check(FOLD_ROWS, "same-results")
        self.assertEqual(1, result.returncode)
        self.assertIn("first-01-30: FULL target " + SECOND, result.stderr)
        self.assertIn("second-01-30: FULL target " + SECOND, result.stderr)

    def test_same_result_and_correct_are_distinct(self):
        first = FOLD_ROWS[0]
        same_wrong = (first, ("13", "cdc-first-01-30", *first[2:]))
        self.assertEqual(0, self.run_check(same_wrong, "same-results").returncode)
        self.assertEqual(1, self.run_check(same_wrong).returncode)

        night = "2026-01-15 20:34:05.123456"
        normal = (("1", "full-winter", night, night, "0.000000", "1"),
                  ("11", "cdc-winter", night, night, "0.000000", "1"))
        self.assertEqual(0, self.run_check(normal).returncode)
        self.assertEqual(0, self.run_check(normal, "same-results").returncode)
        self.assertEqual(0, self.run_check([row[:-1] for row in normal], header=HEADER.rsplit("\t", 1)[0]).returncode)

    def test_both_phases_need_same_input(self):
        result = self.run_check(FOLD_ROWS[:2])
        self.assertEqual(1, result.returncode)
        self.assertIn("capture both", result.stderr)
        result = self.run_check((FOLD_ROWS[0], ("13", "cdc-first-01-30", SECOND, SECOND, "0", "1")))
        self.assertEqual(1, result.returncode)
        self.assertIn("different source UTC values", result.stderr)

    def test_offsets_and_epochs_can_represent_the_same_instant(self):
        utc = "2026-11-01T08:30:00.123456789Z"
        offset = "2026-11-01T01:30:00.123456789-07:00"
        epoch = "1793521800.123456789"
        rows = (("3", "full-fold", utc, epoch, "0", "1"),
                ("13", "cdc-fold", offset, utc.replace("Z", "+00:00"), "0", "1"))
        self.assertEqual(0, self.run_check(rows).returncode)
        self.assertEqual(0, self.run_check(rows, "same-results").returncode)

        shifted = ("13", "cdc-fold", offset, "1793521800.123456790", "0.000000001", "1")
        result = self.run_check((rows[0], shifted), "same-results")
        self.assertEqual(1, result.returncode)
        self.assertIn("CDC target 1793521800.123456790", result.stderr)

    def test_native_readbacks_can_use_short_or_compact_offsets(self):
        utc = "2026-11-01T09:30:00Z"
        rows = (("3", "full-offset", "2026-11-01 09:30:00+00", utc, "0", "1"),
                ("13", "cdc-offset", "2026-11-01 15:00:00+0530", utc, "0", "1"))
        self.assertEqual(0, self.run_check(rows).returncode)

    def test_invalid_readback_and_false_zero_delta_cannot_pass(self):
        invalid = (("3", "full-fold", "bad", "bad", "0", "1"),
                   ("13", "cdc-fold", "bad", "bad", "0", "1"))
        result = self.run_check(invalid)
        self.assertEqual(1, result.returncode)
        self.assertIn("expected a timestamp or numeric epoch", result.stderr)
        false_zero = (("3", "full-fold", FIRST, SECOND, "0", "1"),
                      ("13", "cdc-fold", FIRST, SECOND, "0", "1"))
        result = self.run_check(false_zero, "same-results")
        self.assertEqual(1, result.returncode)
        self.assertIn("delta_seconds disagrees", result.stderr)


if __name__ == "__main__":
    unittest.main()
