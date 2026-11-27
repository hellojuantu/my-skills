#!/usr/bin/env python3
"""Verify saved Console API, requested browser, CHECK, or phase readback evidence."""

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit


IDLE_STATUSES = {"INIT", "STOP", "COMPLETE", "DELETE"}
# The sidecar dispatches ABNORMAL retries and the WAIT_* transitions.
BUSY_STATUSES = {"RUNNING", "WAIT_START", "WAIT_STOP", "WAIT_RESTART", "WAIT_COMPLETE", "ABNORMAL"}
TASK_STATUSES = IDLE_STATUSES | BUSY_STATUSES
UTC_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
ISO_TIMESTAMP = re.compile(
    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})(\.\d{1,9})?(Z|[+-](?:[01]\d|2[0-3])(?::?[0-5]\d)?)?"
)


def read_snapshot(path):
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: cannot read Console JSON ({type(error).__name__})") from error
    if not isinstance(snapshot, dict):
        raise ValueError(f"{path}: expected a Console JSON object")
    return snapshot


def required_id(item, field, where):
    value = item.get(field) if isinstance(item, dict) else None
    if type(value) is not int or value <= 0:
        raise ValueError(f"{where}: missing or invalid {field}")
    return value


def required_list(item, field, where):
    value = item.get(field)
    if not isinstance(value, list):
        raise ValueError(f"{where}: expected a {field} array")
    return value


def task_status(task, where):
    status = task.get("dataTaskStatus")
    if not isinstance(status, str) or status not in TASK_STATUSES:
        raise ValueError(f"{where}: missing or unknown dataTaskStatus")
    return status


def require_idle_job(job, job_id):
    where = f"job {job_id}"
    active = job.get("fsmActive")
    if type(active) is not bool:
        raise ValueError(f"{where}: missing or invalid fsmActive")
    if active:
        raise ValueError(f"{where}: fsmActive=true")
    for task in required_list(job, "dataTasks", where):
        task_id = required_id(task, "dataTaskId", where)
        task_label = f"{where}, task {task_id}"
        status = task_status(task, task_label)
        if status in BUSY_STATUSES:
            raise ValueError(f"{task_label}: {status}")
    for child in required_list(job, "childJobs", where):
        child_id = required_id(child, "dataJobId", f"child of {where}")
        require_idle_job(child, child_id)


API = "/cloudcanal/console/api/v1/inner/datajob/"
LIST_JOBS = API + "listbypage"
QUERY_JOB = API + "queryjob"


def timestamp(value, where):
    if not isinstance(value, str):
        raise ValueError(f"{where}: supply an ISO 8601 timestamp with a UTC offset")
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{where}: invalid timestamp") from error
    if dt.tzinfo is None:
        raise ValueError(f"{where}: timestamp must include a UTC offset")
    return dt


def response_data(snapshot, path, origin, endpoint):
    if browser_route(snapshot, "requestUrl", path) != (origin, endpoint):
        raise ValueError(f"{path}: capture {endpoint} on the expected Console")
    data = snapshot.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a successful Console response data object")
    return data


def worker_snapshot(path, origin, worker, not_before, endpoint):
    snapshot = read_snapshot(path)
    keys = [k for k in ("workerId", "workerIp") if snapshot.get(k) is not None]
    if len(keys) != 1 or str(snapshot[keys[0]]) != worker:
        raise ValueError(f"{path}: capture the selected Worker {worker} using workerId or workerIp")
    captured = timestamp(snapshot.get("capturedAt"), path)
    if captured < not_before or captured > datetime.now(timezone.utc) + timedelta(seconds=30):
        raise ValueError(f"{path}: capture the Worker snapshot during this release")
    return response_data(snapshot, path, origin, endpoint)


def console_origin(origin_url):
    origin, route = browser_route({"origin": origin_url}, "origin", "--origin")
    if route or urlsplit(origin_url).query or urlsplit(origin_url).fragment:
        raise ValueError("--origin: use the Console origin without a page path")
    return origin


def check_idle(pages, supplemental_jobs, origin_url, worker, not_before):
    origin = console_origin(origin_url)
    if not worker.strip() or worker == "0":
        raise ValueError("--worker: select a specific workerId or workerIp")
    not_before = timestamp(not_before, "--not-before")
    listed_ids = set()
    expected_count = None
    for path in pages:
        page = worker_snapshot(path, origin, worker, not_before, LIST_JOBS)
        count = page.get("allJobCounts")
        if type(count) is not int or count < 0:
            raise ValueError(f"{path}: missing or invalid allJobCounts")
        if expected_count is not None and count != expected_count:
            raise ValueError(f"{path}: allJobCounts changed from {expected_count} to {count}; recollect the pages")
        expected_count = count
        jobs = required_list(page, "jobVos", path)
        if not jobs and (count != 0 or len(pages) != 1):
            raise ValueError(f"{path}: unexpected empty page; recollect the pages")
        for job in jobs:
            job_id = required_id(job, "dataJobId", path)
            if job_id in listed_ids:
                raise ValueError(f"{path}: duplicate listed job {job_id}; recollect the pages")
            listed_ids.add(job_id)
            require_idle_job(job, job_id)
    if len(listed_ids) != expected_count:
        raise ValueError(f"received {len(listed_ids)} listed jobs, expected {expected_count}; recollect the pages")

    supplemental_ids = set()
    for path in supplemental_jobs:
        job = worker_snapshot(path, origin, worker, not_before, QUERY_JOB)
        job_id = required_id(job, "dataJobId", path)
        if job_id in supplemental_ids:
            raise ValueError(f"{path}: duplicate supplemental job {job_id}")
        supplemental_ids.add(job_id)
        require_idle_job(job, job_id)
    print(f"Worker snapshots idle ({len(listed_ids)} listed jobs, {len(supplemental_ids)} supplemental snapshots)")


def check_completion(path):
    job = read_snapshot(path)
    job_id = required_id(job, "dataJobId", path)
    where = f"{path}, job {job_id}"
    checks = []
    for task in required_list(job, "dataTasks", where):
        task_id = required_id(task, "dataTaskId", where)
        task_type = task.get("dataTaskType")
        if not isinstance(task_type, str) or not task_type:
            raise ValueError(f"{where}, task {task_id}: missing or invalid dataTaskType")
        if task_type == "CHECK":
            checks.append((task_id, task))
    if len(checks) != 1:
        raise ValueError(f"{where}: expected one CHECK task, found {len(checks)}")
    task_id, task = checks[0]
    task_label = f"{where}, CHECK task {task_id}"
    status = task_status(task, task_label)
    if status != "COMPLETE":
        raise ValueError(f"{task_label}: {status}; waiting for COMPLETE")
    raw_time = task.get("completeTime")
    if not isinstance(raw_time, str):
        raise ValueError(f"{task_label}: missing or invalid completeTime")
    if raw_time.endswith("Z"):
        raw_time = raw_time[:-1] + "+00:00"
    try:
        complete_time = datetime.fromisoformat(raw_time)
    except ValueError as error:
        raise ValueError(f"{task_label}: invalid completeTime") from error
    if complete_time.tzinfo is None:
        raise ValueError(f"{task_label}: completeTime must include a UTC offset")
    return job_id, task_id, complete_time


def check_fresh(after, before, new_job_id):
    job_id, task_id, complete_time = check_completion(after)
    if before is not None:
        previous_id, _, previous_time = check_completion(before)
        if job_id != previous_id:
            raise ValueError(f"replay job ID changed from {previous_id} to {job_id}")
        if complete_time <= previous_time:
            raise ValueError(f"job {job_id}, CHECK task {task_id}: stale COMPLETE at {complete_time.isoformat()}; "
                             f"expected a completion after {previous_time.isoformat()}")
    elif job_id != new_job_id:
        raise ValueError(f"expected new job {new_job_id}, got job {job_id}")
    print(f"job {job_id}, CHECK task {task_id}: fresh COMPLETE at {complete_time.isoformat()}")


def browser_route(record, field, where):
    value = record.get(field)
    if not isinstance(value, str):
        raise ValueError(f"{where}: missing {field}")
    url = urlsplit(value)
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
        raise ValueError(f"{where}: expected a Console URL in {field}")
    if field == "requestUrl" and url.fragment:
        raise ValueError(f"{where}: expected an HTTP request URL without a fragment")
    route = urlsplit(url.fragment).path if field == "pageUrl" and url.fragment.startswith("/") else url.path
    return (url.scheme, url.hostname, url.port), route.rstrip("/")


def jpeg_has_frame(file):
    file.seek(0)
    if file.read(2) != b"\xff\xd8":
        return False
    has_dimensions = False
    while file.read(1) == b"\xff":
        marker = file.read(1)
        while marker == b"\xff":
            marker = file.read(1)
        length = int.from_bytes(file.read(2), "big")
        if not marker or length < 2:
            return False
        if marker == b"\xda":  # Start of scan.
            return has_dimensions
        if marker[0] in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
            frame = file.read(5)
            if length < 8 or len(frame) < 5 or min(int.from_bytes(frame[1:3], "big"), int.from_bytes(frame[3:5], "big")) == 0:
                return False
            has_dimensions = True
            file.seek(length - 7, 1)
        else:
            file.seek(length - 2, 1)
    return False


def check_detail_screenshot(directory):
    candidates = [directory / name for name in ("detail.png", "detail.jpg", "detail.jpeg")]
    files = [path for path in candidates if path.is_file()]
    if len(files) != 1:
        raise ValueError(f"{directory}: save exactly one detail.png or detail.jpg screenshot")
    path = files[0]
    try:
        with path.open("rb") as file:
            header = file.read(24)
            file.seek(-12, 2)
            tail = file.read(12)
            if path.suffix == ".png":
                valid = (header[:16] == bytes.fromhex("89504e470d0a1a0a0000000d49484452")
                         and int.from_bytes(header[16:20], "big") > 0 and int.from_bytes(header[20:24], "big") > 0
                         and tail == bytes.fromhex("0000000049454e44ae426082"))
            else:
                valid = tail.endswith(bytes.fromhex("ffd9")) and jpeg_has_frame(file)
    except OSError as error:
        raise ValueError(f"{path}: save a complete detail screenshot") from error
    if len(header) != 24 or not valid:
        raise ValueError(f"{path}: screenshot bytes must match its PNG or JPEG extension")


def created_job(create_path):
    create = read_snapshot(create_path)
    job_id = required_id(create, "dataJobId", create_path)
    origin, endpoint = browser_route(create, "requestUrl", create_path)
    if endpoint != API + "create":
        raise ValueError(f"{create_path}: record the Console create API request")
    status = create.get("httpStatus")
    if (create.get("method") != "POST" or type(status) is not int or not 200 <= status < 300
            or str(create.get("code")) != "1"):
        raise ValueError(f"{create_path}: expected a successful create API response")
    return create, origin, job_id


def check_started_job(query, origin, job_id):
    job = response_data(read_snapshot(query), query, origin, QUERY_JOB)
    if required_id(job, "dataJobId", query) != job_id:
        raise ValueError(f"{query}: query the job returned by create, job {job_id}")
    tasks = required_list(job, "dataTasks", query)
    if not all(isinstance(task, dict) and task.get("dataTaskType") for task in tasks):
        raise ValueError(f"{query}: expected dataTaskType for every task")
    for task in tasks:
        required_id(task, "dataTaskId", query)
    # Async creation can finish BUILD_STRUCT before the operator starts a sync.
    work_tasks = [task for task in tasks if task["dataTaskType"] != "BUILD_STRUCT"] or tasks
    if not any(task.get("dataTaskStatus") in {"RUNNING", "COMPLETE"} for task in work_tasks):
        raise ValueError(f"{query}: capture job {job_id} with a RUNNING or COMPLETE work task after starting it")


def check_api_job(directory, query):
    _create, origin, job_id = created_job(directory / "create.json")
    check_started_job(query, origin, job_id)
    print(f"API creation and started-task evidence match job {job_id}; verify native target readback separately")


def check_browser_job(directory, query):
    create_path = directory / "create.json"
    create, origin, job_id = created_job(create_path)
    if browser_route(create, "pageUrl", create_path) != (origin, "/data/job/create/process"):
        raise ValueError(f"{create_path}: record the creation request from the Console wizard")
    detail_path = directory / "detail.json"
    detail = read_snapshot(detail_path)
    if browser_route(detail, "pageUrl", detail_path) != (origin, f"/data/job/{job_id}"):
        raise ValueError(f"{detail_path}: open job {job_id} on the same Console and capture its detail page")
    check_detail_screenshot(directory)
    check_started_job(query, origin, job_id)
    print(f"Browser creation, detail and started-task evidence match job {job_id}")


def check_stopped_test_job(query, origin_url, job_id):
    job = response_data(read_snapshot(query), query, console_origin(origin_url), QUERY_JOB)
    if required_id(job, "dataJobId", query) != job_id:
        raise ValueError(f"{query}: capture queryjob for the new test job {job_id}")
    increment_ids = []
    for task in required_list(job, "dataTasks", query):
        task_id = required_id(task, "dataTaskId", query)
        task_type = task.get("dataTaskType")
        if not isinstance(task_type, str) or not task_type:
            raise ValueError(f"job {job_id}, task {task_id}: capture dataTaskType")
        if task_type == "INCREMENT":
            where = f"job {job_id}, INCREMENT task {task_id}"
            status = task_status(task, where)
            if status != "STOP":
                raise ValueError(f"{where} is {status}. Stop the test job and query again until STOP")
            increment_ids.append(str(task_id))
    if not increment_ids:
        raise ValueError(f"job {job_id}: expected an INCREMENT task. Check the test job ID and its dataTasks")
    if job.get("fsmActive") is not False:
        raise ValueError(f"job {job_id}: query the stopped job again and capture fsmActive=false")
    print(f"job {job_id}: fsmActive=false, INCREMENT tasks {', '.join(increment_ids)} STOP")


def readback_seconds(text, where):
    match = ISO_TIMESTAMP.fullmatch(text)
    try:
        if match:
            time, fraction, offset = match.groups()
            if offset in (None, "Z"):
                offset = "+00:00"
            else:
                offset = offset.replace(":", "").ljust(5, "0")
                offset = offset[:3] + ":" + offset[3:]
            difference = datetime.fromisoformat(time + offset) - UTC_EPOCH
            return Decimal(difference.days * 86400 + difference.seconds) + Decimal(fraction or "0")
        seconds = Decimal(text)
        if seconds.is_finite():
            return seconds
    except (InvalidOperation, ValueError):
        pass
    raise ValueError(f"{where}: expected a timestamp or numeric epoch in seconds")


@dataclass(frozen=True)
class PhaseSample:
    source: Decimal
    target: Decimal
    source_text: str
    target_text: str
    delta: Decimal
    datetime_equal: bool


def check_phase_readback(path, expect):
    fields = {"phase", "source_utc", "target_utc", "delta_seconds"}
    pairs = {}
    try:
        with path.open(encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source, delimiter="\t")
            if not fields.issubset(reader.fieldnames or []):
                raise ValueError(f"{path}: expected phase, source_utc, target_utc and delta_seconds columns")
            for row in reader:
                where = f"{path}:{reader.line_num}"
                phase, _, case = (row["phase"] or "").partition("-")
                if phase not in {"full", "cdc"} or not case:
                    raise ValueError(f"{where}: use full-<case> or cdc-<case> in the phase column")
                results = pairs.setdefault(case, {})
                if phase in results:
                    raise ValueError(f"{where}: duplicate {phase}-{case} sample")
                try:
                    delta = Decimal(row["delta_seconds"] or "")
                except InvalidOperation as error:
                    raise ValueError(f"{where}: expected a numeric delta_seconds") from error
                datetime_equal = row.get("datetime_equal", "1")
                if not delta.is_finite() or not row["source_utc"] or not row["target_utc"] or datetime_equal not in {"0", "1"}:
                    raise ValueError(f"{where}: missing native source or target readback")
                source_seconds = readback_seconds(row["source_utc"], f"{where} source_utc")
                target_seconds = readback_seconds(row["target_utc"], f"{where} target_utc")
                if target_seconds - source_seconds != delta:
                    raise ValueError(f"{where}: delta_seconds disagrees with the native readbacks")
                results[phase] = PhaseSample(source_seconds, target_seconds, row["source_utc"], row["target_utc"],
                                             delta, datetime_equal == "1")
    except (OSError, UnicodeError, csv.Error) as error:
        raise ValueError(f"{path}: cannot read phase TSV ({type(error).__name__})") from error

    if not pairs:
        raise ValueError(f"{path}: expected at least one full and CDC sample pair")
    errors = []
    for case, results in pairs.items():
        if results.keys() != {"full", "cdc"}:
            raise ValueError(f"{path}: capture both full-{case} and cdc-{case} with the same source value")
        full, cdc = results["full"], results["cdc"]
        if full.source != cdc.source:
            raise ValueError(f"{path}: full-{case} and cdc-{case} have different source UTC values")
        for phase, sample in results.items():
            if not sample.datetime_equal:
                errors.append(f"{phase}-{case}: DATETIME differs from source. Retain actual values to compare phases")
            if expect == "correct" and sample.delta != 0:
                errors.append(f"{phase}-{case}: source {sample.source_text}, target {sample.target_text}, delta {sample.delta} s")
        if expect == "same-results" and full.target != cdc.target:
            errors.append(f"{case}: FULL target {full.target_text} ({full.delta} s), CDC target {cdc.target_text} ({cdc.delta} s)")
    if errors:
        raise ValueError(f"{path}: phase readback mismatches\n" + "\n".join(errors))
    print(f"Paired FULL and CDC readbacks satisfy {expect} ({len(pairs)} pairs)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    idle = commands.add_parser("idle", help="Check worker-scoped list-jobs pages and supplemental query-job snapshots")
    idle.add_argument("--origin", required=True, help="Console origin for the release")
    idle.add_argument("--worker", required=True, help="Selected workerId or workerIp")
    idle.add_argument("--not-before", required=True, help="Release claim time including UTC offset")
    idle.add_argument("pages", nargs="+", type=Path)
    idle.add_argument("--job", action="append", type=Path, default=[], help="Additional query-job snapshot, repeatable")
    api = commands.add_parser("api-job", help="Default acceptance: match API creation and started query-job without page evidence")
    api.add_argument("directory", type=Path, help="API evidence directory containing create.json")
    api.add_argument("query", type=Path, help="Query-job requestUrl and response data captured after start")
    browser = commands.add_parser("browser-job", help="When the user requests pages: match wizard, detail and started query-job")
    browser.add_argument("directory", type=Path, help="Browser capture directory with create.json, detail.json and a detail PNG or JPEG")
    browser.add_argument("query", type=Path, help="Query-job requestUrl and response data captured after start")
    stopped = commands.add_parser("stopped-test-job", help="Check a new incremental test job after stopping it")
    stopped.add_argument("--origin", required=True, help="Console origin used to create the test job")
    stopped.add_argument("--job-id", type=int, required=True, help="Job ID returned when creating the test job")
    stopped.add_argument("query", type=Path, help="Query-job requestUrl and response data captured after stop")
    fresh = commands.add_parser("fresh-check", help="Check the completion of a replayed or newly created CHECK job")
    fresh.add_argument("after", type=Path)
    provenance = fresh.add_mutually_exclusive_group(required=True)
    provenance.add_argument("--before", type=Path, help="Query the same job before replay")
    provenance.add_argument("--new-job-id", type=int, help="Job ID returned when creating a fresh CHECK job")
    phases = commands.add_parser("phase-readback", help="Verify paired FULL and CDC target readbacks")
    phases.add_argument("tsv", type=Path, help="Native readback TSV with full-<case> and cdc-<case> phases")
    phases.add_argument("--expect", choices=("correct", "same-results"), default="correct")
    args = parser.parse_args()

    try:
        if args.command == "idle":
            check_idle(args.pages, args.job, args.origin, args.worker, args.not_before)
        elif args.command == "api-job":
            check_api_job(args.directory, args.query)
        elif args.command == "browser-job":
            check_browser_job(args.directory, args.query)
        elif args.command == "stopped-test-job":
            check_stopped_test_job(args.query, args.origin, args.job_id)
        elif args.command == "phase-readback":
            check_phase_readback(args.tsv, args.expect)
        else:
            check_fresh(args.after, args.before, args.new_job_id)
    except ValueError as error:
        print(f"Console job snapshots: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
