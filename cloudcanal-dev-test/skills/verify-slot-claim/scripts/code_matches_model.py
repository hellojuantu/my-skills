#!/usr/bin/env python3
"""Run the slot-claim behavior SlotClaim.tla models."""

from contextlib import contextmanager
import importlib.util
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace


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


def observe_locks(module):
    calls = []
    real = module.slot_lock

    @contextmanager
    def wrapped(private, slot, exclusive=True):
        calls.append(bool(exclusive))
        with real(private, slot, exclusive=exclusive):
            yield

    module.slot_lock = wrapped
    return calls, real


def check_change_claim_takes_write_lock(module, private):
    calls, real = observe_locks(module)
    try:
        result = module.change_claim(acquire_args(), private, {"01": {"consolePort": 8111}})
    finally:
        module.slot_lock = real
    if not result.get("ok"):
        return "acquire failed"
    if True not in calls:
        return "change_claim does not hold the write lock"
    return ""


def check_status_takes_read_lock(module, private):
    calls, real = observe_locks(module)
    try:
        module.status(private, {"01": {"consolePort": 8111}})
    finally:
        module.slot_lock = real
    if not calls or any(calls):
        return "status does not hold the read lock"
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
