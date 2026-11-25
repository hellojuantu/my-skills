#!/usr/bin/env python3
"""Run the slot-claim behavior SlotClaim.tla models."""

from contextlib import ExitStack, contextmanager
import importlib.util
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def load_claim(path):
    spec = importlib.util.spec_from_file_location("slot_claim_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def acquire_args():
    return SimpleNamespace(
        command="acquire", slot="01", new_slot=False, access="write",
        machine="Pro", agent="Codex", hostname="pro.local",
        run_id="release-1", branch="test",
        session_id="s", session_title="t", session_url=None,
        claim_id=None, phase=None, job_id=None, note=None, reason=None,
    )


def check_lock(module, private):
    started = threading.Event()
    release = threading.Event()

    def hold():
        with module.slot_lock(private, "01"):
            started.set()
            release.wait(timeout=2)

    holder = threading.Thread(target=hold)
    holder.start()
    if not started.wait(timeout=2):
        return "slot_lock did not enter"
    acquired = threading.Event()

    def second():
        with module.slot_lock(private, "01"):
            acquired.set()

    other = threading.Thread(target=second)
    other.start()
    blocked = not acquired.wait(timeout=0.3)
    release.set()
    other.join(timeout=2)
    holder.join(timeout=2)
    if not blocked:
        return "slot_lock does not exclude another caller"
    if not acquired.is_set():
        return "slot_lock did not release the next caller"
    return ""


@contextmanager
def observe_locks(module):
    held = {}
    real = module.slot_lock

    @contextmanager
    def wrapped(private, slot, exclusive=True):
        with real(private, slot, exclusive=exclusive):
            key = private / f".claim-{slot}"
            held[key] = (exclusive, object())
            try:
                yield
            finally:
                del held[key]

    with patch.object(module, "slot_lock", wrapped):
        yield held


def check_change_claim_takes_write_lock(module, private):
    args = acquire_args()
    directory = private / f".claim-{args.slot}"
    registered = {args.slot: {"consolePort": 8111}}
    events = []
    read_claim, mkdir, replace, rename = module.read_claim, Path.mkdir, Path.replace, Path.rename

    def read(path):
        if path == directory:
            events.append(("read", held.get(directory)))
        return read_claim(path)

    def create(path, *args, **kwargs):
        if path == directory:
            events.append(("mkdir", held.get(directory)))
        return mkdir(path, *args, **kwargs)

    def publish(path, target):
        if target == directory / "owner.json":
            events.append(("publish", held.get(directory)))
        return replace(path, target)

    def archive(path, target):
        if path == directory:
            events.append(("archive", held.get(directory)))
        return rename(path, target)

    with observe_locks(module) as held, ExitStack() as patches:
        patches.enter_context(patch.object(module, "read_claim", read))
        patches.enter_context(patch.object(Path, "mkdir", create))
        patches.enter_context(patch.object(Path, "replace", publish))
        patches.enter_context(patch.object(Path, "rename", archive))
        for command, expected in (("acquire", ["read", "mkdir", "publish"]),
                                  ("update", ["read", "publish"]), ("release", ["read", "archive"])):
            args.command = command
            args.phase = "testing"
            args.reason = "completed"
            events.clear()
            result = module.change_claim(args, private, registered)
            if not result.get("ok"):
                return f"{command} failed"
            if [operation for operation, _ in events] != expected:
                return f"{command} did not perform the expected claim operations: {expected}"
            read_lock = events[0][1]
            if read_lock is None or not read_lock[0] or any(lock != read_lock for _, lock in events):
                return f"change_claim does not hold the write lock across {command}"
            if command == "acquire":
                args.claim_id = result["claim"]["claimId"]
    return ""


def check_status_takes_read_lock(module, private):
    registered = {"01": {"consolePort": 8111}, "02": {"consolePort": 8112}}
    expected = {private / f".claim-{slot}" for slot in registered}
    reads = {}
    real_read = module.read_claim

    def read(directory):
        reads[directory] = {path: lock for path, (exclusive, lock) in held.items() if not exclusive}
        return real_read(directory)

    with observe_locks(module) as held, patch.object(module, "read_claim", read):
        module.status(private, registered)
    if reads.keys() != expected or any(locks.keys() != expected for locks in reads.values()):
        return "status does not hold the read lock for every slot in the snapshot"
    first, second = reads.values()
    if first != second:
        return "status released a read lock between slots in the snapshot"
    return ""


def check_claims(module, private):
    registered = {"01": {"consolePort": 8111}}
    args = acquire_args()
    first = module.change_claim(args, private, registered)
    if not first.get("ok"):
        return "acquire failed"
    claim_id = first["claim"]["claimId"]
    again = module.change_claim(args, private, registered)
    if again.get("ok") or (again.get("claim") or {}).get("claimId") != claim_id:
        return "acquire replaced an existing claim"
    args.command = "release"
    args.claim_id = "0" * 32
    args.reason = "completed"
    stale = module.change_claim(args, private, registered)
    if stale.get("ok") or not (private / ".claim-01").is_dir():
        return "a different claimId released the current claim"
    return ""


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3] / "scripts/slot_claim.py"
    module = load_claim(path)
    problems = []
    for check in (check_lock, check_status_takes_read_lock, check_change_claim_takes_write_lock, check_claims):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private"
            private.mkdir()
            problem = check(module, private)
            if problem:
                problems.append(problem)
    if problems:
        print(f"{path} no longer matches SlotClaim.tla:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print(f"{path} still keeps one claim under the slot lock and rejects a different claimId")
    return 0


if __name__ == "__main__":
    sys.exit(main())
