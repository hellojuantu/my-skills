from cc_console.utils import parse_int, print_json


LIST_CONSOLE_JOBS_PATH = "/cloudcanal/console/api/v1/inner/consolejob/list"
QUERY_CONSOLE_JOB_PATH = "/cloudcanal/console/api/v1/inner/consolejob/queryconsolejob"
RETRY_CONSOLE_TASK_PATH = "/cloudcanal/console/api/v1/inner/consolejob/retrytask"
SKIP_CONSOLE_TASK_PATH = "/cloudcanal/console/api/v1/inner/consolejob/skiptask"
CANCEL_CONSOLE_JOB_PATH = "/cloudcanal/console/api/v1/inner/consolejob/cancel"


def query_console_job(client, console_job_id):
    response = client.post_json(QUERY_CONSOLE_JOB_PATH, {"consoleJobId": parse_int(console_job_id, "consoleJobId")})
    return client.ensure_success(response, "query console job")


def failed_console_tasks(console_job):
    return [task for task in console_job.get("taskVOList") or [] if task.get("taskState") == "FAILED"]


def console_job_failure_summary(console_job):
    failed = failed_console_tasks(console_job)
    return {
        "consoleJobId": console_job.get("id"),
        "label": console_job.get("label"),
        "taskState": console_job.get("taskState"),
        "resourceType": console_job.get("resourceType"),
        "resourceId": console_job.get("resourceId"),
        "dataJobName": console_job.get("dataJobName"),
        "failedTasks": [
            {
                "id": task.get("id"),
                "stepName": task.get("stepName"),
                "handlerBeanName": task.get("handlerBeanName"),
                "message": task.get("message"),
            }
            for task in failed
        ],
    }


def list_console_jobs_cmd(args, client):
    payload = {
        "consoleTaskState": args.state or "",
        "label": args.label or "",
        "startId": int(args.start_id or 0),
        "pageSize": int(args.page_size or 20),
    }
    response = client.post_json(LIST_CONSOLE_JOBS_PATH, payload)
    print_json(client.ensure_success(response, "list console jobs") or [])
    return 0


def query_console_job_cmd(args, client):
    data = query_console_job(client, args.console_job_id)
    if args.summary:
        print_json(console_job_failure_summary(data))
    else:
        print_json(data)
    return 0


def operate_console_task_cmd(args, client):
    payload = {
        "consoleJobId": parse_int(args.console_job_id, "consoleJobId"),
        "consoleTaskId": parse_int(args.console_task_id, "consoleTaskId") if args.console_task_id else "",
    }
    path = {
        "retry": RETRY_CONSOLE_TASK_PATH,
        "skip": SKIP_CONSOLE_TASK_PATH,
        "cancel": CANCEL_CONSOLE_JOB_PATH,
    }[args.action]
    if args.dry_run:
        print_json({"path": path, "payload": payload})
        return 0
    response = client.post_json(path, payload)
    client.ensure_success(response, args.action + " console job")
    print("Console job operation finished, action=" + args.action + ", id=" + str(payload["consoleJobId"]))
    return 0
