#!/usr/bin/env python3
"""Run a test command in an existing Mini directory and return its exit code."""

import argparse
from pathlib import Path
import secrets
import shlex
import subprocess
import sys


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

    directory = args.workdir.removeprefix('~/') if args.workdir != '~' else '.'
    receipt = 'CC_MINI_TEST_' + secrets.token_hex(12)
    remote = f'cd -- {shlex.quote(directory)} && CC_MINI_TEST_RECEIPT={receipt} sh -s -- {shlex.join(command)}'
    runner = Path(__file__).with_name('run-mini-test.sh')
    # Mini's SSH service can return zero after a failed remote command. Read the runner's own status.
    status = None
    with runner.open('rb') as script, subprocess.Popen(
        ['ssh', '-T', '-o', 'BatchMode=yes', 'mini', remote], stdin=script, stderr=subprocess.PIPE
    ) as ssh:
        prefix = (receipt + '=').encode()
        for line in ssh.stderr:
            if line.startswith(prefix) and line[len(prefix):].strip().isdigit():
                status = int(line[len(prefix):])
            else:
                sys.stderr.buffer.write(line)
                sys.stderr.buffer.flush()
        transport_status = ssh.wait()
    if status is None:
        print('Mini did not return a test exit code. Check the SSH connection and Mini working directory.', file=sys.stderr)
        return transport_status or 1
    print(f'CloudCanal test exit: {status}', file=sys.stderr)
    return status or transport_status


if __name__ == '__main__':
    sys.exit(main())
