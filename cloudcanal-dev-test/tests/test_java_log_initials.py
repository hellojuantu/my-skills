from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check_java_log_initials.py"


class JavaLogInitialsTest(unittest.TestCase):
    def check(self, code):
        with TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "Example.java").write_text(code, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CHECKER), "--repo", str(repo), "Example.java"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.stderr, "", result.stderr)
            return result

    def test_reports_body_after_bracket_label_at_its_own_line(self):
        result = self.check('''class Example {
    static final String TAG = "[Reader] ";
    void run() {
        LOG.info(TAG +
                "lowercase log body");
        LOG.info(TAG + "Uppercase log body");
    }
}''')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertIn("Example.java:5:", result.stdout)
        self.assertIn("'Lowercase'", result.stdout)

    def test_skips_body_when_prefix_contains_text_or_is_dynamic(self):
        result = self.check('''class Example {
    static final String WORD = "Reader ";
    static final String DYNAMIC = "[Reader]" + activity();
    void run(String prefix) {
        LOG.info(WORD + "lowercase word");
        LOG.info(DYNAMIC + "lowercase word");
        LOG.info(prefix + "lowercase word");
    }
}''')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_skips_reassigned_variable_and_shadowed_field(self):
        result = self.check('''class Example {
    static final String TAG = "[Reader] ";
    void run(String TAG) {
        String tag = "[Reader] ";
        { tag = "Reading "; }
        LOG.info(tag + "the value");
        LOG.info(TAG + "the value");
    }
}''')
        self.assertEqual(result.returncode, 0, result.stdout)
