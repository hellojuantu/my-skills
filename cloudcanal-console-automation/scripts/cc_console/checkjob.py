import json
import time

from cc_console.datajob import active_fsm_job, job_action_result, job_name, query_job, start_job
from cc_console.utils import parse_int, print_json


def tasks_by_type(job):
    return {task.get("dataTaskType"): task for task in job.get("dataTasks") or []}


def should_active_fsm(job):
    build_task = tasks_by_type(job).get("BUILD_STRUCT")
    increment_task = tasks_by_type(job).get("INCREMENT") or {}
    build_ready = not build_task or build_task.get("dataTaskStatus") == "COMPLETE"
    return (
        build_ready
        and not job.get("fsmActive")
        and (
            job.get("dataTaskState") == "INIT"
            or job.get("currTaskStatus") == "INIT"
            or (
                full_complete(job)
                and increment_task.get("dataTaskStatus") in (None, "INIT", "STOP")
            )
        )
    )


def full_complete(job):
    build_task = tasks_by_type(job).get("BUILD_STRUCT") or {}
    full_task = tasks_by_type(job).get("FULL") or {}
    return (
        job.get("lifeCycleState") == "CREATED"
        and build_task.get("dataTaskStatus") in (None, "COMPLETE")
        and full_task.get("dataTaskStatus") in (None, "COMPLETE")
    )


def parse_task_position(task):
    value = task.get("taskPosition")
    if not value:
        return {}
    try:
        position = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return position if isinstance(position, dict) else {}


def summarize_check_job(job):
    tasks = []
    child_ok = True
    task_statuses = []
    for task in job.get("dataTasks") or []:
        if task.get("dataTaskType") != "CHECK":
            continue
        task_statuses.append(task.get("dataTaskStatus"))
        position = parse_task_position(task)
        loss = position.get("loss")
        diff = position.get("diff")
        task_ok = type(loss) is int and loss == 0 and type(diff) is int and diff == 0
        child_ok = child_ok and task_ok and task.get("dataTaskStatus") == "COMPLETE"
        tasks.append(
            {
                "taskId": task.get("dataTaskId"),
                "type": task.get("dataTaskType"),
                "status": task.get("dataTaskStatus"),
                "totalToCheck": position.get("totalToCheck"),
                "checked": position.get("checked"),
                "checkedPercent": position.get("checkedPercent"),
                "loss": loss,
                "diff": diff,
            }
        )
    if task_statuses:
        child_complete = all(status == "COMPLETE" for status in task_statuses)
    else:
        child_complete = job.get("dataTaskState") == "COMPLETE"
    if job.get("haveException") or job.get("consoleTaskState") == "FAILED":
        child_ok = False
    return {
        "jobId": job.get("dataJobId"),
        "jobName": job_name(job),
        "state": job.get("dataTaskState"),
        "currTaskStatus": job.get("currTaskStatus"),
        "consoleTaskState": job.get("consoleTaskState"),
        "fsmActive": job.get("fsmActive"),
        "haveException": job.get("haveException"),
        "complete": child_complete,
        "ok": bool(tasks) and child_ok,
        "tasks": tasks,
    }


def check_job_running(job):
    if job.get("currTaskStatus") == "RUNNING":
        return True
    return any(task.get("dataTaskStatus") == "RUNNING" for task in job.get("dataTasks") or [])


def check_job_waiting_start(job):
    if job.get("currTaskStatus") == "WAIT_START":
        return True
    return any(task.get("dataTaskStatus") == "WAIT_START" for task in job.get("dataTasks") or [])


def check_job_complete(job):
    summary = summarize_check_job(job)
    return bool(summary.get("complete"))


def check_job_startable(job):
    if check_job_running(job) or check_job_complete(job):
        return False
    if job.get("haveException") or job.get("consoleTaskState") == "FAILED":
        return False
    return job.get("currTaskStatus") == "STOP" or any(task.get("dataTaskStatus") == "STOP" for task in job.get("dataTasks") or [])


def ensure_check_jobs_running(client, job_ids):
    actions = []
    for job_id in job_ids or []:
        job = query_job(client, job_id)
        if check_job_waiting_start(job):
            actions.append({"jobId": job_id, "action": "wait-start", "reason": "task already submitted to CloudCanal scheduler"})
            continue
        if job.get("fsmActive") and not check_job_running(job) and not check_job_complete(job):
            actions.append({"jobId": job_id, "action": "wait-active-fsm", "reason": "fsm is active; wait for CloudCanal scheduler"})
            continue
        try:
            if should_active_fsm(job):
                result = active_fsm_job(client, job_id)
                action = "active-fsm"
            elif check_job_startable(job):
                result = start_job(client, job_id)
                action = "start"
            else:
                continue
            actions.append({"jobId": job_id, "action": action, "result": result})
        except Exception as e:
            refreshed = query_job(client, job_id)
            if check_job_waiting_start(refreshed):
                actions.append({"jobId": job_id, "action": "wait-start-after-start-rejected", "startError": str(e)})
                continue
            if not check_job_running(refreshed) and not check_job_complete(refreshed):
                raise
            actions.append({"jobId": job_id, "action": "already-running-after-error", "error": str(e)})
    return actions


def wait_check_jobs(client, job_ids, timeout_seconds):
    deadline = time.time() + max(int(timeout_seconds or 0), 1)
    last = []
    wanted = [int(job_id) for job_id in job_ids or []]
    actions = []
    while time.time() < deadline:
        actions.extend(ensure_check_jobs_running(client, wanted))
        last = []
        for job_id in wanted:
            last.append(summarize_check_job(query_job(client, job_id)))
        if last and all(child.get("complete") for child in last):
            return {"complete": True, "ok": all(child.get("ok") for child in last), "children": last, "startActions": actions}
        time.sleep(5)
    return {"complete": False, "ok": False, "children": last, "startActions": actions}


def wait_check_job_cmd(args, client):
    result = wait_check_jobs(client, [parse_int(job_id, "jobId") for job_id in args.job_id], args.timeout_seconds)
    print_json(result)
    return 0 if result.get("ok") else 2


def replay_check_job_cmd(args, client):
    ids = [parse_int(job_id, "jobId") for job_id in args.job_id]
    replay_results = []
    for job_id in ids:
        replay_results.append(job_action_result(client, "replay", job_id))
    if args.wait_before_seconds:
        time.sleep(args.wait_before_seconds)
    result = wait_check_jobs(client, ids, args.timeout_seconds)
    result["replayResults"] = replay_results
    print_json(result)
    return 0 if result.get("ok") else 2
