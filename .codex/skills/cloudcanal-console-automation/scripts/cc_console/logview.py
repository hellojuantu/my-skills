import json

from cc_console.datajob import query_job
from cc_console.utils import maybe_read_value_file, parse_int, print_json


TAIL_TASK_LOG_PATH = "/cloudcanal/console/api/v1/inner/logview/tail/tasklog"
TAIL_WORKER_LOG_PATH = "/cloudcanal/console/api/v1/inner/logview/tail/workerlog"
GREP_OPERATION_LOG_PATH = "/cloudcanal/console/api/v1/inner/logview/grep/operationlog"

TASK_STATE_TO_TYPE = {
    "BUILD_STRUCT": "BUILD_STRUCT",
    "FULL": "FULL",
    "INCRE": "INCREMENT",
    "INCREMENT": "INCREMENT",
    "CATCH_UP": "INCREMENT",
    "CHECK": "CHECK",
    "REVISE": "REVISE",
}


def read_json_arg(value, default=None):
    if value in (None, ""):
        return default
    text = maybe_read_value_file(value)
    return json.loads(text)


def deep_merge(base, extra):
    if not extra:
        return base
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def shifted_end_row(end_row, step):
    end_row = int(end_row or 0)
    step = int(step or 0)
    if step == 0 or end_row + step < 0:
        return 0
    return end_row + step


def task_type_value(value):
    if not value:
        return None
    normalized = str(value).strip().upper()
    if normalized == "INCRE":
        return "INCREMENT"
    return normalized


def resolve_task_id(client, job_id, task_id=None, task_type=None):
    if task_id:
        return parse_int(task_id, "taskId")

    job = query_job(client, job_id)
    tasks = job.get("dataTasks") or []
    wanted_type = task_type_value(task_type)
    if not wanted_type:
        wanted_type = TASK_STATE_TO_TYPE.get(str(job.get("dataTaskState") or job.get("currTaskStatus") or "").upper())

    if wanted_type:
        for task in tasks:
            if task_type_value(task.get("dataTaskType")) == wanted_type:
                return parse_int(task.get("dataTaskId"), "taskId")

    for task in tasks:
        if task.get("dataTaskStatus") != "COMPLETE":
            return parse_int(task.get("dataTaskId"), "taskId")
    if tasks:
        return parse_int(tasks[0].get("dataTaskId"), "taskId")
    raise ValueError("taskId not found for jobId " + str(job_id))


def filter_log_files(logs, file_name=None, contains=None):
    result = []
    for item in logs or []:
        if file_name and item.get("fileName") != file_name:
            continue
        if contains:
            content = str(item.get("content") or "")
            matched_lines = [line for line in content.splitlines() if contains in line]
            if not matched_lines:
                continue
            item = dict(item)
            item["content"] = "\n".join(matched_lines)
        result.append(item)
    return result


def print_log_text(logs):
    for idx, item in enumerate(logs or []):
        if idx:
            print()
        print("===== " + str(item.get("fileName") or "log") + " =====")
        if item.get("desc"):
            print("desc: " + str(item.get("desc")))
        if item.get("path"):
            print("path: " + str(item.get("path")))
        if item.get("endRow") is not None:
            print("endRow: " + str(item.get("endRow")))
        print()
        print(item.get("content") or "")


def tail_task_log_cmd(args, client):
    job_id = parse_int(args.job_id, "dataJobId")
    task_id = resolve_task_id(client, job_id, args.task_id, args.task_type)
    payload = {
        "taskId": task_id,
        "dataJobId": job_id,
        "endRow": shifted_end_row(args.end_row, args.step),
    }
    deep_merge(payload, read_json_arg(args.payload_json, {}))
    if args.dry_run:
        print_json({"path": TAIL_TASK_LOG_PATH, "payload": payload})
        return 0

    data = client.ensure_success(client.post_json(TAIL_TASK_LOG_PATH, payload), "tail task log") or []
    data = filter_log_files(data, args.file_name, args.contains)
    if args.text:
        print_log_text(data)
    else:
        print_json(data)
    return 0


def tail_worker_log_cmd(args, client):
    payload = {
        "workerId": parse_int(args.worker_id, "workerId"),
        "endRow": shifted_end_row(args.end_row, args.step),
    }
    if args.log_type:
        payload["fetchedLogTypeList"] = args.log_type
    deep_merge(payload, read_json_arg(args.payload_json, {}))
    if args.dry_run:
        print_json({"path": TAIL_WORKER_LOG_PATH, "payload": payload})
        return 0

    data = client.ensure_success(client.post_json(TAIL_WORKER_LOG_PATH, payload), "tail worker log") or []
    data = filter_log_files(data, args.file_name, args.contains)
    if args.text:
        print_log_text(data)
    else:
        print_json(data)
    return 0


def grep_operation_log_cmd(args, client):
    payload = {}
    if args.operation_id:
        payload["operationId"] = parse_int(args.operation_id, "operationId")
    deep_merge(payload, read_json_arg(args.payload_json, {}))
    if args.dry_run:
        print_json({"path": GREP_OPERATION_LOG_PATH, "payload": payload})
        return 0
    print_json(client.ensure_success(client.post_json(GREP_OPERATION_LOG_PATH, payload), "grep operation log"))
    return 0
