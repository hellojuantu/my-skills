#!/usr/bin/env python3
"""Run a test command in an existing Mini directory and return its exit code."""

import argparse
from pathlib import Path
import secrets
import shlex
import subprocess
import sys

from mini_names import MINI_NAME_KEYS, mini_env_path, read_values
from ssh_auth import SshAuthReporter


def load_mini_env():
    path = mini_env_path()
    if not path.is_file():
        print(f"Copy cloudcanal-dev-test/skills/cc-setup/mini.env.example to {path} and fill it in.", file=sys.stderr)
        return None
    values = read_values(path)
    missing = [key for key in (*MINI_NAME_KEYS, "MINI_SSH_USER") if not values.get(key)]
    if missing:
        print(f"{path} is missing {', '.join(missing)}", file=sys.stderr)
        return None
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', default='.', help='Working directory on Mini (relative to its home, or absolute)')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        parser.error('supply a test command')

    mini = load_mini_env()
    if mini is None:
        return 1
    directory = args.workdir.removeprefix('~/') if args.workdir != '~' else '.'
    receipt = 'CC_MINI_TEST_' + secrets.token_hex(12)
    names = " ".join(f"CC_{key}={shlex.quote(mini[key])}" for key in MINI_NAME_KEYS)
    remote = (
        f'cd -- {shlex.quote(directory)} && CC_MINI_TEST_RECEIPT={receipt} '
        f'{names} sh -s -- {shlex.join(command)}'
    )
    runner = Path(__file__).with_name('run-mini-test.sh')
    # Mini's SSH service can return zero after a failed remote command. Read the runner's own status.
    status = None
    refused = False
    auth = SshAuthReporter()
    with runner.open('rb') as script, subprocess.Popen(
        ['ssh', '-T', '-o', 'BatchMode=yes', mini['MINI_SSH_HOST'], remote], stdin=script, stderr=subprocess.PIPE
    ) as ssh:
        prefix = (receipt + '=').encode()
        for line in ssh.stderr:
            if line.startswith(prefix) and line[len(prefix):].strip().isdigit():
                status = int(line[len(prefix):])
            else:
                if b'CloudCanal test refused' in line:
                    refused = True
                sys.stderr.buffer.write(line)
                sys.stderr.buffer.flush()
                auth.observe(line.decode("utf-8", errors="replace"))
        transport_status = ssh.wait()
    if status is None and refused:
        return 1
    if status is None and auth.url is not None:
        return transport_status or 1
    if status is None:
        print('Mini did not return a test exit code. Check the SSH connection and Mini working directory.', file=sys.stderr)
        return transport_status or 1
    print(f'CloudCanal test exit: {status}', file=sys.stderr)
    return status or transport_status


if __name__ == '__main__':
    sys.exit(main())
