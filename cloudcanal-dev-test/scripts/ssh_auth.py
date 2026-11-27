#!/usr/bin/env python3
"""Report the browser action required by a Tailscale SSH check."""

import argparse
import re
import sys


class SshAuthReporter:
    def __init__(self):
        self.url = None

    def observe(self, message):
        if self.url is not None:
            return
        match = re.search(r"https://login\.tailscale\.com/a/[A-Za-z0-9_-]+", message)
        if match is None:
            return
        self.url = match.group(0)
        print(
            "Mini SSH authentication required.\n"
            f"CUA: open {self.url} in Google Chrome; choose Google and select an already signed-in Google account.\n"
            "Continue until the page shows Authorization successful, then retry the original SSH command.\n"
            "A Google account chooser is an agent action. Request user takeover only when the page requires "
            "password, MFA, CAPTCHA, or another action the agent cannot complete.\n"
            "Use CUA for the browser steps; keep browser automation out of shell scripts.\n"
            "Workflow: cloudcanal-dev-test/skills/cc-setup/SKILL.md#mini-ssh-身份复核",
            file=sys.stderr, flush=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message", nargs="?", help="SSH stderr or the authentication URL; otherwise read stdin")
    args = parser.parse_args()
    reporter = SshAuthReporter()
    reporter.observe(args.message if args.message is not None else sys.stdin.read())
    if reporter.url is None:
        print("No Tailscale SSH authentication URL found. Keep the original SSH error for diagnosis.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
