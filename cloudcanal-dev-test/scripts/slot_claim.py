#!/usr/bin/env python3
"""Inspect and manage CloudCanal release claims on Mini."""

import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import socket
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import uuid


SERVICE_ROOT = Path.home() / "datasource-lab/cloudcanal-service"
MINI_ENV_KEYS = ("MINI_SSH_HOST", "MINI_SSH_USER", "MINI_TAILSCALE_NAME", "MINI_HOSTNAME")


def load_mini_env():
    path = Path(__file__).resolve().parents[1] / "skills" / "cc-setup" / "mini.env"
    if not path.is_file():
        raise ValueError(f"Copy cloudcanal-dev-test/skills/cc-setup/mini.env.example to {path} and fill it in.")
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    missing = [key for key in MINI_ENV_KEYS if not values.get(key)]
    if missing:
        raise ValueError(f"{path} is missing {', '.join(missing)}")
    return values
PHASES = ("reserved", "deploying", "testing", "awaiting-handoff")


def valid_slot(value):
    return re.fullmatch(r"0[1-9]|[1-9][0-9]+", value) is not None


def slot_number(value):
    if not valid_slot(value):
        raise argparse.ArgumentTypeError("use a slot number such as 01 or 03")
    return value


def session_url(value):
    url = urlsplit(value)
    if url.scheme not in {"http", "https", "codex", "claude"} or not url.netloc or url.username:
        raise argparse.ArgumentTypeError("use a direct session URL without embedded credentials")
    return value


def job_id(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("use a positive job ID")
    return number


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--on-mini", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="List registered slots and their claims")
    acquire = commands.add_parser("acquire", help="Reserve a slot and record its owner")
    acquire.add_argument("slot", type=slot_number)
    acquire.add_argument("--new-slot", action="store_true", help="Reserve an unregistered slot the user requested")
    acquire.add_argument("--machine", choices=("Air", "Pro", "Mini", "Other"), required=True)
    acquire.add_argument("--agent", choices=("Codex", "Claude", "Manual"), required=True)
    acquire.add_argument("--hostname", help=argparse.SUPPRESS)
    acquire.add_argument("--run-id", required=True)
    acquire.add_argument("--branch", required=True)
    acquire.add_argument("--session-id")
    acquire.add_argument("--session-title")
    acquire.add_argument("--access", choices=("read", "write"), required=True, help="read: create or verify tasks. write: replace JARs or publish.")
    acquire.add_argument("--session-url", type=session_url)
    update = commands.add_parser("update", help="Record progress or an outstanding handoff")
    update.add_argument("slot", type=slot_number)
    update.add_argument("--claim-id", required=True)
    update.add_argument("--phase", choices=PHASES)
    update.add_argument("--job-id", type=job_id, action="append")
    update.add_argument("--note")
    update.add_argument("--access", choices=("read", "write"), help="Change this claim between task verification and JAR publish.")
    release = commands.add_parser("release", help="Archive and release the specified claim")
    release.add_argument("slot", type=slot_number)
    release.add_argument("--claim-id", required=True)
    release.add_argument("--user-confirmed", action="store_true", required=True,
                         help="The user explicitly requested release of this claim")
    return parser.parse_args()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def legacy_claim(directory, directory_stat):
    owner_path = directory / "owner"
    try:
        raw = owner_path.read_bytes()
    except FileNotFoundError:
        raw = b""
    fields = {}
    old_timestamp = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            fields[key.strip()] = value.strip()
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}T[0-9:.]+Z", line):
            old_timestamp = line
    identity = (directory_stat.st_dev, directory_stat.st_ino, directory_stat.st_ctime_ns)
    digest = hashlib.sha256(repr(identity).encode() + raw).hexdigest()
    return {
        "claimId": f"legacy-{digest[:32]}", "legacy": True,
        "agent": fields.get("agent") or fields.get("executor"), "machine": None, "hostname": None,
        "sessionId": None, "sessionTitle": None, "sessionUrl": None,
        "runId": fields.get("release") or fields.get("case"), "branch": fields.get("branch"),
        "claimedAt": fields.get("claimedAt") or fields.get("claimed_at") or old_timestamp,
        "updatedAt": None, "phase": "unknown", "access": None, "jobIds": [], "note": None,
    }


def read_claim(directory):
    try:
        directory_stat = directory.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise ValueError(f"{directory.name} is not a claim directory")
    owner_path = directory / "owner.json"
    try:
        owner = json.loads(owner_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return legacy_claim(directory, directory_stat)
    if not isinstance(owner, dict) or not re.fullmatch(r"[0-9a-f]{32}", str(owner.get("claimId"))):
        raise ValueError(f"{directory.name} has invalid owner.json metadata")
    return owner


def write_owner(directory, owner):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(owner, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.close()
            temporary.replace(directory / "owner.json")
        finally:
            temporary.unlink(missing_ok=True)


@contextmanager
def slot_lock(private, slot, exclusive=True):
    locks = private / ".claim-locks"
    locks.mkdir(mode=0o700, exist_ok=True)
    # Keep the lock outside the claim directory so the same slot lock survives an archive or reacquire.
    with (locks / slot).open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield


def status(private, registered):
    claimed = {path.name.removeprefix(".claim-") for path in private.glob(".claim-*")}
    slot_numbers = sorted(filter(valid_slot, registered.keys() | claimed), key=lambda value: (len(value), value))
    slots = []
    with ExitStack() as locks:
        for slot in slot_numbers:
            locks.enter_context(slot_lock(private, slot, exclusive=False))
        for slot in slot_numbers:
            try:
                claim = read_claim(private / f".claim-{slot}")
            except (OSError, ValueError) as error:
                claim = {"claimId": None, "phase": "unknown", "error": str(error)}
            slots.append({"slot": slot, "consolePort": registered.get(slot, {}).get("consolePort"), "claim": claim})
    all_registered_claimed = bool(registered) and all(row["claim"] is not None for row in slots if row["slot"] in registered)
    result = {"ok": True, "slots": slots, "allRegisteredClaimed": all_registered_claimed}
    if all_registered_claimed:
        result["nextAction"] = "ask-user-to-review-sessions"
    return result


def acquire_claim(args, directory):
    now = utc_now()
    owner = {
        "claimId": uuid.uuid4().hex, "legacy": False,
        "machine": args.machine, "hostname": args.hostname or socket.gethostname(), "agent": args.agent,
        "sessionId": args.session_id, "sessionTitle": args.session_title, "sessionUrl": args.session_url,
        "runId": args.run_id, "branch": args.branch, "phase": "reserved", "access": args.access, "jobIds": [], "note": None,
        "claimedAt": now, "updatedAt": now,
    }
    directory.mkdir(mode=0o700)
    try:
        write_owner(directory, owner)
    except (OSError, ValueError):
        directory.rmdir()
        raise
    return owner


def change_claim(args, private, registered):
    slot = args.slot
    directory = private / f".claim-{slot}"
    with slot_lock(private, slot, exclusive=True):
        owner = read_claim(directory)
        if args.command == "acquire":
            if owner is not None:
                return {"ok": False, "slot": slot, "error": "Slot is already claimed", "claim": owner}
            if slot not in registered and not args.new_slot:
                raise ValueError(f"Slot {slot} is not registered. Use --new-slot for a planned new slot.")
            return {"ok": True, "slot": slot, "claim": acquire_claim(args, directory)}

        if owner is None or owner["claimId"] != args.claim_id:
            return {"ok": False, "slot": slot, "error": "Claim ID changed or the slot was released", "claim": owner}
        if args.command == "update":
            if owner["legacy"]:
                raise ValueError("Legacy claims can only be released after confirming the prior run ended")
            for field, value in (("phase", args.phase), ("jobIds", args.job_id), ("note", args.note), ("access", args.access)):
                if value is not None:
                    owner[field] = value
            if owner.get("phase") == "deploying" and owner.get("access") != "write":
                raise ValueError(f"Slot {slot} deployment requires a write claim. Use --access write.")
            owner["updatedAt"] = utc_now()
            write_owner(directory, owner)
            return {"ok": True, "slot": slot, "claim": owner}

        if not args.user_confirmed:
            raise ValueError("Release requires an explicit user request. Keep the claim awaiting-handoff.")
        history = private / "claim-history"
        history.mkdir(mode=0o700, exist_ok=True)
        archive = history / f"{slot}-{args.claim_id}"
        if archive.exists():
            raise ValueError("This claim already has an archive. Verify the slot state before releasing it.")
        directory.rename(archive)
        return {"ok": True, "slot": slot, "claimId": args.claim_id, "archivePath": str(archive), "reason": "user-confirmed"}


def expected_mini_host():
    try:
        configured = load_mini_env()["MINI_HOSTNAME"]
    except ValueError:
        configured = ""
    passed = os.environ.get("CC_MINI_HOSTNAME", "")
    if configured and passed and passed != configured:
        raise ValueError("CC_MINI_HOSTNAME does not match mini.env")
    if configured:
        return configured
    if passed:
        return passed
    raise ValueError("Copy cloudcanal-dev-test/skills/cc-setup/mini.env.example to mini.env and fill it in.")


def on_mini(args):
    host = socket.gethostname().split(".", 1)[0]
    if host != expected_mini_host():
        raise ValueError("Claim files must be managed on the machine named in cloudcanal-dev-test/skills/cc-setup/mini.env")
    root = (args.root or SERVICE_ROOT).resolve()
    registered = json.loads((root / "slots.json").read_text(encoding="utf-8"))
    if not isinstance(registered, dict) or any(not valid_slot(slot) or not isinstance(entry, dict)
                                               for slot, entry in registered.items()):
        raise ValueError("Expected slots.json to map slot numbers to registry entries")
    private = root / "private"
    if not private.is_dir():
        raise ValueError("Mini slot private directory is missing")
    if args.command == "status":
        return status(private, registered)
    return change_claim(args, private, registered)


def forward_to_mini(args):
    from ssh_auth import SshAuthReporter

    if args.root is not None:
        raise ValueError("An alternate root is only supported when running directly on Mini")
    command = ["/usr/bin/python3", "-", "--on-mini", *sys.argv[1:]]
    if args.command == "acquire":
        command.extend(["--hostname", socket.gethostname()])
        if not args.session_id:
            if args.agent == "Codex":
                session_id = os.environ.get("CODEX_THREAD_ID")
            elif args.agent == "Claude":
                session_id = os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")
            else:
                session_id = None
            if session_id:
                command.extend(["--session-id", session_id])
    env = load_mini_env()
    remote = f"CC_MINI_HOSTNAME={shlex.quote(env['MINI_HOSTNAME'])} {shlex.join(command)}"
    auth = SshAuthReporter()
    # The script is also sent to Mini alone, so the local browser helper is imported only above.
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as source, tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as output:
        source.write(Path(__file__).read_text(encoding="utf-8"))
        source.seek(0)
        with subprocess.Popen(
            ["ssh", "-T", "-o", "BatchMode=yes", env["MINI_SSH_HOST"], remote],
            stdin=source, stdout=output, stderr=subprocess.PIPE, text=True,
        ) as ssh:
            for line in ssh.stderr:
                print(line, end="", file=sys.stderr, flush=True)
                auth.observe(line)
            transport_status = ssh.wait()
        output.seek(0)
        reply_text = output.read()
    try:
        reply = json.loads(reply_text)
        if isinstance(reply, dict) and type(reply.get("ok")) is bool:
            print(reply_text, end="")
            return transport_status or int(not reply["ok"])
    except ValueError:
        pass
    if auth.url is not None:
        return transport_status or 1
    print("Mini did not return a claim result", file=sys.stderr)
    return transport_status or 1


def main():
    args = arguments()
    try:
        if not args.on_mini:
            return forward_to_mini(args)
        reply = on_mini(args)
    except (OSError, ValueError) as error:
        reply = {"ok": False, "error": str(error)}
    print(json.dumps(reply, ensure_ascii=False, indent=2))
    return int(not reply["ok"])


if __name__ == "__main__":
    sys.exit(main())
