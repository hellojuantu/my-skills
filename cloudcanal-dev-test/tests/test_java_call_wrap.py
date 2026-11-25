from pathlib import Path
import os
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check_java_call_wrap.py"
BAD_CALL = """\
            return createDruidDs( //
                    config.getHost(), //
                    dbName, //
                    connProps, //
                    null, //
                    false);
"""
GOOD_CALL = """\
            return createDruidDs( //
                    config.getHost(), //
                    dbName, //
                    connProps, //
                    null, //
                    false //
            );
"""


class JavaCallWrapTest(unittest.TestCase):
    def check(self, source, original="        int x = 1;\n", name="Example.java", untracked=False):
        with TemporaryDirectory() as directory:
            repo = Path(directory)
            env = {
                **os.environ,
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            }
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, env=env)
            java = repo / name
            java.write_text("class Example {\n    void create() {\n" + original + "    }\n}\n", encoding="utf-8")
            if not untracked:
                subprocess.run(["git", "add", name], cwd=repo, check=True, env=env)
            subprocess.run(["git", "commit", "--allow-empty", "-m", "base"], cwd=repo, check=True, capture_output=True, env=env)
            java.write_text("class Example {\n    void create() {\n" + source + "    }\n}\n", encoding="utf-8")
            return subprocess.run([sys.executable, str(CHECKER), "--repo", str(repo)], capture_output=True, text=True)

    def test_rejects_closing_paren_on_the_last_argument(self):
        result = self.check(BAD_CALL)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Example.java:", result.stderr)
        self.assertIn("false);", result.stderr)

    def test_accepts_last_argument_comment_and_separate_close(self):
        result = self.check(GOOD_CALL)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_removed_argument_comment_in_existing_call(self):
        for argument in ("dbName,", "false"):
            with self.subTest(argument=argument):
                edited = GOOD_CALL.replace(argument + " //", argument)
                result = self.check(edited, original=GOOD_CALL)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(argument, result.stderr)

    def test_ignores_untouched_bad_call_in_changed_file(self):
        result = self.check(BAD_CALL + "        unrelated();\n", original=BAD_CALL)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ignores_sql_in_text_block_and_checks_following_java(self):
        sql = '        String sql = """\n            SELECT GET_VALUE( //\n            id)\n            """;\n'
        self.assertEqual(self.check(sql).returncode, 0)
        result = self.check(sql + BAD_CALL)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(len(result.stderr.splitlines()), 1)
        self.assertIn("false);", result.stderr)

    def test_checks_space_in_tracked_and_untracked_filename(self):
        for untracked in (True, False):
            with self.subTest(untracked=untracked):
                result = self.check(BAD_CALL, name="With Space.java", untracked=untracked)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("With Space.java:", result.stderr)
