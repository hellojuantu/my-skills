import subprocess
import unittest
from pathlib import Path


GUARD = Path(__file__).resolve().parents[1] / 'scripts' / 'run-mini-test.sh'


class MiniRunnerTest(unittest.TestCase):
    def run_guard(self, host, command):
        shell = 'hostname() { printf "%s\\n" "$TEST_HOST"; }\n' + GUARD.read_text()
        return subprocess.run(['/bin/sh', '-s', '--', *command], env={'TEST_HOST': host},
                              input=shell, capture_output=True, text=True)

    def test_rejects_local_oracle_test_before_gradle_starts(self):
        result = self.run_guard('juantus-MacBook-Pro', ['./gradlew', '--offline', ':ds-oracle:test'])
        self.assertEqual(result.returncode, 1)
        self.assertIn('CloudCanal test refused on juantus-MacBook-Pro', result.stderr)
        self.assertNotIn('CloudCanal test exit', result.stderr)

    def test_keeps_remote_test_failure(self):
        result = self.run_guard('clougences-Mac-mini', ['/bin/sh', '-c', 'exit 17'])
        self.assertEqual(result.returncode, 17)
        self.assertIn('CloudCanal test exit=17', result.stderr)


if __name__ == '__main__':
    unittest.main()
