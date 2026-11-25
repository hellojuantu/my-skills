import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


GUARD = Path(__file__).resolve().parents[1] / 'scripts' / 'run-mini-test.sh'


class MiniRunnerTest(unittest.TestCase):
    def run_guard(self, host, command, expected=None):
        shell = 'hostname() { printf "%s\\n" "$TEST_HOST"; }\n' + GUARD.read_text()
        env = {'TEST_HOST': host}
        if expected is not None:
            env['CC_MINI_HOSTNAME'] = expected
        return subprocess.run(['/bin/sh', '-s', '--', *command], env=env,
                              input=shell, capture_output=True, text=True)

    def test_runner_forwards_all_configured_names_to_a_clean_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / 'local' / 'scripts'
            remote = root / 'remote' / 'scripts'
            config = local.parent / 'skills' / 'cc-setup' / 'mini.env'
            local.mkdir(parents=True)
            remote.mkdir(parents=True)
            config.parent.mkdir(parents=True)
            for name in ('run_mini_test.py', 'mini_names.py', GUARD.name):
                shutil.copy2(GUARD.with_name(name), local)
            shutil.copy2(GUARD.with_name('mini_names.py'), remote)
            hostname = subprocess.check_output(['hostname', '-s'], text=True).strip()
            config.write_text(f'MINI_HOSTNAME={hostname}\nMINI_SSH_HOST=test-alias\n'
                              'MINI_TAILSCALE_NAME=box.private.test\nMINI_SSH_USER=test\n')
            ssh = root / 'ssh'
            ssh.write_text('#!/bin/sh\nfor arg do command=$arg; done\nexec /bin/sh -c "$command"\n')
            ssh.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'])
            for key in ('CC_MINI_HOSTNAME', 'CC_MINI_SSH_HOST', 'CC_MINI_TAILSCALE_NAME'):
                env.pop(key, None)
            result = subprocess.run([
                sys.executable, local / 'run_mini_test.py', '--workdir', remote, '--', sys.executable, '-c',
                'import json, mini_names; print(json.dumps(sorted(mini_names.console_names()[1])))',
            ], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(set(json.loads(result.stdout)), {hostname.lower(), 'test-alias', 'box.private.test'})

    def test_rejects_local_oracle_test_before_gradle_starts(self):
        result = self.run_guard('juantus-MacBook-Pro', ['./gradlew', '--offline', ':ds-oracle:test'])
        self.assertEqual(result.returncode, 1)
        self.assertIn('CloudCanal test refused on juantus-MacBook-Pro', result.stderr)
        self.assertNotIn('CloudCanal test exit', result.stderr)

    def test_keeps_remote_test_failure(self):
        result = self.run_guard('test-mini', ['/bin/sh', '-c', 'exit 17'], expected='test-mini')
        self.assertEqual(result.returncode, 17)
        self.assertIn('CloudCanal test exit=17', result.stderr)


if __name__ == '__main__':
    unittest.main()
