import json
import os
import re
import shlex
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from types import SimpleNamespace

from cc_console.client import ApiError, ConsoleClient, json_part
from cc_console.clusters import resolve_cluster_id
from cc_console.consolejob import console_job_failure_summary, query_console_job
from cc_console.datajob import (
    ADD_CHECK_CHILD_JOB_PATH,
    CREATE_JOB_PATH,
    active_fsm_job,
    build_datajob_payload,
    failed_prechecks,
    job_action_result,
    job_name,
    precheck,
    precheck_title,
    query_job,
    query_job_schema,
    start_job,
)
from cc_console.datasource import LIST_BY_CONDITION_PATH, normalize_ds_type, query_datasource, read_json_arg
from cc_console.db_adapters import MYSQL_DEFAULT_PROFILE, adapter_for_pair, adapter_for_type, adapter_reports, install_dependency_commands
from cc_console.logview import TAIL_TASK_LOG_PATH
from cc_console.utils import mask_payload, parse_int, print_json


PLAN_OUTLINE = [
    ("结构迁移", "P1", "单主键表、联合主键表、无主键表、唯一键表、全类型表、断点续传"),
    ("全量迁移", "P1", "单表、多表、修改订阅、断点续传、停止启动重跑、校验/订正子任务"),
    ("增量同步", "P1", "单表、多表、修改订阅、位点重置、断点续传、常用 DDL、配置变更"),
    ("数据校验订正", "P1", "单表、多表、一次性/周期性校验订正、重跑、模拟不一致"),
    ("特殊表设置", "P1", "目标主键、虚拟列、过滤条件、映射规则"),
    ("映射规则", "P1", "表名/列名映射、批量自定义表名、前缀后缀、修改订阅后映射"),
    ("其他补充", "P1/P2", "全库同步、action 过滤、按条件/表名筛选、性能指标、库表映射"),
]


class AutotestRunError(Exception):
    def __init__(self, message, run=None, phase=None):
        super().__init__(message)
        self.run = run
        self.phase = phase


MYSQL_DETAIL_COVERAGE = [
    {"case": "单表结构迁移-单int主键", "profile": MYSQL_DEFAULT_PROFILE, "table": "pk_int_table", "auto": True},
    {"case": "单表结构迁移-单int主键（自增）", "profile": MYSQL_DEFAULT_PROFILE, "table": "pk_int_auto_table", "auto": True},
    {"case": "单表结构迁移-单varchar主键", "profile": MYSQL_DEFAULT_PROFILE, "table": "pk_varchar_table", "auto": True},
    {"case": "单表结构迁移-单timestamp主键", "profile": MYSQL_DEFAULT_PROFILE, "table": "pk_timestamp_table", "auto": True},
    {"case": "多表结构迁移-各类型表", "profile": MYSQL_DEFAULT_PROFILE, "table": "*", "auto": True},
    {"case": "多表全量迁移-各类型表", "profile": MYSQL_DEFAULT_PROFILE, "table": "*", "auto": True},
    {"case": "多表-各个类型表数据同步", "profile": MYSQL_DEFAULT_PROFILE, "table": "*", "auto": True},
    {"case": "多表数据校验-一次性校验", "profile": MYSQL_DEFAULT_PROFILE, "table": "*", "auto": True},
]


def parse_json_field(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def table_auto_create_flags(source_schema):
    flags = {}
    for db_obj in source_schema or []:
        for table in db_obj.get("tables") or []:
            if "table" in table:
                flags[table.get("table")] = bool(table.get("targetAutoCreate"))
        for schema_obj in db_obj.get("schemas") or []:
            for table in schema_obj.get("tables") or []:
                flags[table.get("table")] = bool(table.get("targetAutoCreate"))
        for schema_obj in db_obj.get("tableSpaces") or []:
            for table in schema_obj.get("tables") or []:
                flags[table.get("table")] = bool(table.get("targetAutoCreate"))
    return flags


def table_column_counts(source_schema):
    counts = {}
    for db_obj in source_schema or []:
        for table in db_obj.get("tables") or []:
            if "table" in table:
                counts[table.get("table")] = len(table.get("columns") or [])
        for schema_obj in db_obj.get("schemas") or []:
            for table in schema_obj.get("tables") or []:
                counts[table.get("table")] = len(table.get("columns") or [])
        for schema_obj in db_obj.get("tableSpaces") or []:
            for table in schema_obj.get("tables") or []:
                counts[table.get("table")] = len(table.get("columns") or [])
    return counts


def has_explicit_autotest_tables(args):
    return bool(getattr(args, "table", None) or getattr(args, "table_map", None))


def source_table_name(value):
    text = str(value or "").strip()
    if "=" in text:
        text = text.split("=", 1)[0].strip()
    parts = [part for part in text.split(".") if part]
    return parts[-1] if parts else text


def target_table_name(value):
    text = str(value or "").strip()
    if "=" in text:
        text = text.split("=", 1)[1].strip()
    parts = [part for part in text.split(".") if part]
    return parts[-1] if parts else text


def explicit_autotest_tables(args):
    tables = []
    for value in getattr(args, "table", None) or []:
        name = source_table_name(value)
        if name and name not in tables:
            tables.append(name)
    for value in getattr(args, "table_map", None) or []:
        name = source_table_name(value)
        if name and name not in tables:
            tables.append(name)
    return tables


def selected_autotest_tables(args, adapter):
    explicit = explicit_autotest_tables(args)
    if explicit:
        return explicit
    return adapter.profile_tables_for_namespace(args.profile, getattr(args, "source_schema", None))


def explicit_autotest_table_pairs(args):
    pairs = []
    target_table = getattr(args, "target_table", None)
    for value in getattr(args, "table", None) or []:
        source = source_table_name(value)
        target = target_table_name(value) if "=" in str(value) else (target_table or source)
        if source:
            pairs.append((source, target))
    for value in getattr(args, "table_map", None) or []:
        source = source_table_name(value)
        target = target_table_name(value)
        if source:
            pairs.append((source, target or source))
    return pairs


def selected_autotest_table_pairs(args, adapter):
    explicit = explicit_autotest_table_pairs(args)
    if explicit:
        return explicit
    return [(table, table) for table in adapter.profile_tables_for_namespace(args.profile, getattr(args, "source_schema", None))]


def tasks_by_type(job):
    return {task.get("dataTaskType"): task for task in job.get("dataTasks") or []}


def task_status(job, task_type):
    task = tasks_by_type(job).get(task_type) or {}
    return task.get("dataTaskStatus")


def task_type_value(value):
    if not value:
        return None
    normalized = str(value).strip().upper()
    if normalized == "INCRE":
        return "INCREMENT"
    return normalized


def job_brief(job):
    return {
        "jobId": job.get("dataJobId"),
        "lifeCycleState": job.get("lifeCycleState"),
        "state": job.get("dataTaskState"),
        "currTaskStatus": job.get("currTaskStatus"),
        "fsmActive": job.get("fsmActive"),
        "haveException": job.get("haveException"),
        "consoleJobId": job.get("consoleJobId"),
        "consoleTaskState": job.get("consoleTaskState"),
        "consoleJobLabel": job.get("consoleJobLabel"),
        "tasks": [
            {
                "taskId": item.get("dataTaskId"),
                "type": item.get("dataTaskType"),
                "status": item.get("dataTaskStatus"),
                "health": item.get("healthLevel"),
                "conditionHealthStatus": item.get("conditionHealthStatus"),
            }
            for item in job.get("dataTasks") or []
        ],
        "unfinishedFullTables": unfinished_full_tables(job),
    }


def task_unhealthy(task):
    if not task:
        return False
    return task.get("healthLevel") not in (None, "", "Health") or task.get("conditionHealthStatus") in ("UNHEALTHY", "ERROR")


def task_failed(task):
    if not task:
        return False
    status = str(task.get("dataTaskStatus") or "").upper()
    if status in ("FAIL", "FAILED", "ERROR", "EXCEPTION"):
        return True
    if task.get("exceptionMsg") or task.get("errorMsg"):
        return True
    return False


def job_has_task_exception(job):
    if job.get("haveException"):
        return True
    return any(task_failed(task) for task in job.get("dataTasks") or [])


def unfinished_full_tables(job):
    full_task = tasks_by_type(job).get("FULL") or {}
    position = parse_task_position(full_task)
    detail = position.get("transTableDetail")
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except (TypeError, ValueError):
            detail = None
    tables = []
    if isinstance(detail, dict):
        for value in detail.values():
            if not isinstance(value, dict):
                continue
            if value.get("finished") and value.get("flushedToTarget"):
                continue
            tables.append(
                {
                    "schema": value.get("schema"),
                    "table": value.get("tableName"),
                    "handled": value.get("handledRecordCount"),
                    "max": value.get("maxCount"),
                    "percentage": value.get("percentage"),
                    "flushedToTarget": value.get("flushedToTarget"),
                    "currentPk": value.get("currentPk"),
                }
            )
    return tables


def wait_datajob_create_finished(client, job_id, timeout_seconds):
    deadline = time.time() + max(int(timeout_seconds or 0), 1)
    last = None
    while time.time() < deadline:
        job = query_job(client, job_id)
        last = job_brief(job)
        console_state = job.get("consoleTaskState")
        if console_state == "FAILED":
            summary = None
            if job.get("consoleJobId"):
                try:
                    summary = console_job_failure_summary(query_console_job(client, job.get("consoleJobId")))
                except Exception as e:
                    summary = {"error": str(e)}
            raise ApiError(
                "data job create console task failed, last="
                + json.dumps(last, ensure_ascii=False)
                + ",consoleJob="
                + json.dumps(summary, ensure_ascii=False)
            )
        if job.get("lifeCycleState") == "CREATED" and console_state in (None, "SUCCESS"):
            return job
        if console_state == "SUCCESS" and job.get("dataTasks"):
            return job
        time.sleep(3)
    raise ApiError("data job create console task did not finish, last=" + json.dumps(last, ensure_ascii=False))


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


def should_start(job):
    if should_active_fsm(job) or job.get("fsmActive"):
        return False
    return any(task.get("dataTaskStatus") == "STOP" for task in job.get("dataTasks") or [] if task.get("dataTaskType") != "BUILD_STRUCT")


def continue_or_start_job(client, job_id, timeout_seconds):
    deadline = time.time() + max(int(timeout_seconds or 0), 1)
    last = None
    last_error = None
    while time.time() < deadline:
        job = query_job(client, job_id)
        last = job_brief(job)
        if should_active_fsm(job):
            return {"action": "active-fsm", "before": last, "result": active_fsm_job(client, job_id)}
        if should_start(job):
            try:
                return {"action": "start", "before": last, "result": start_job(client, job_id)}
            except Exception as e:
                last_error = str(e)
        if job.get("fsmActive") and (job.get("currTaskStatus") in ("RUNNING", "WAIT_START") or job.get("dataTaskState") in ("FULL", "INCRE", "CATCH_UP")):
            return {"action": "already-active", "before": last}
        time.sleep(3)
    raise ApiError("job did not reach a startable state, last=" + json.dumps(last, ensure_ascii=False) + ",error=" + str(last_error))


def increment_ready(job):
    increment_task = tasks_by_type(job).get("INCREMENT") or {}
    full_task = tasks_by_type(job).get("FULL") or {}
    return (
        job.get("lifeCycleState") == "CREATED"
        and job.get("dataTaskState") in ("CATCH_UP", "INCRE")
        and job.get("currTaskStatus") == "RUNNING"
        and increment_task.get("dataTaskStatus") == "RUNNING"
        and full_task.get("dataTaskStatus") in (None, "COMPLETE")
    )


def full_complete(job):
    build_task = tasks_by_type(job).get("BUILD_STRUCT") or {}
    full_task = tasks_by_type(job).get("FULL") or {}
    return (
        job.get("lifeCycleState") == "CREATED"
        and build_task.get("dataTaskStatus") in (None, "COMPLETE")
        and full_task.get("dataTaskStatus") in (None, "COMPLETE")
    )


def wait_full_complete(client, job_id, timeout_seconds):
    deadline = time.time() + max(int(timeout_seconds or 0), 1)
    last = None
    while time.time() < deadline:
        job = query_job(client, job_id)
        last = job_brief(job)
        if job.get("consoleTaskState") == "FAILED":
            raise ApiError("job console task failed while waiting full complete, last=" + json.dumps(last, ensure_ascii=False))
        if job_has_task_exception(job):
            raise ApiError("job task exception while waiting full complete, last=" + json.dumps(last, ensure_ascii=False))
        if full_complete(job):
            return last
        time.sleep(3)
    raise ApiError("job did not reach full complete, last=" + json.dumps(last, ensure_ascii=False))


def wait_increment_ready(client, job_id, timeout_seconds):
    deadline = time.time() + max(int(timeout_seconds or 0), 1)
    last = None
    fsm_activated = False
    while time.time() < deadline:
        job = query_job(client, job_id)
        last = job_brief(job)
        if job.get("consoleTaskState") == "FAILED":
            raise ApiError("job console task failed while waiting increment ready, last=" + json.dumps(last, ensure_ascii=False))
        if job_has_task_exception(job):
            raise ApiError("job task exception while waiting increment ready, last=" + json.dumps(last, ensure_ascii=False))
        if should_active_fsm(job) and not fsm_activated:
            active_fsm_job(client, job_id)
            fsm_activated = True
            time.sleep(3)
            continue
        if increment_ready(job):
            return last
        time.sleep(3)
    raise ApiError("job did not reach increment ready before faker CRUD, last=" + json.dumps(last, ensure_ascii=False))


def parse_task_position(task):
    value = task.get("taskPosition")
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


def check_child_summary(job):
    children = []
    for child in job.get("childJobs") or []:
        children.append(summarize_check_job(child))
    return children


def summarize_check_job(job):
    tasks = []
    child_ok = True
    task_statuses = []
    for task in job.get("dataTasks") or []:
        task_statuses.append(task.get("dataTaskStatus"))
        position = parse_task_position(task)
        loss = position.get("loss")
        diff = position.get("diff")
        task_ok = (loss in (None, 0)) and (diff in (None, 0))
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
        child_complete = job.get("dataTaskState") == "COMPLETE" or job.get("currTaskStatus") == "COMPLETE"
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
        "errorMsg": job.get("errorMsg") or job.get("exceptionMsg"),
        "complete": child_complete,
        "ok": child_ok,
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


def wait_check_child(client, job_id, timeout_seconds):
    deadline = time.time() + max(int(timeout_seconds or 0), 1)
    last = []
    actions = []
    while time.time() < deadline:
        job = query_job(client, job_id)
        last = check_child_summary(job)
        child_ids = child_ids_from_check_result({"children": last})
        if child_ids:
            actions.extend(ensure_check_jobs_running(client, child_ids))
            last = [summarize_check_job(query_job(child_id)) for child_id in child_ids]
        if last and all(child.get("complete") for child in last):
            return {"complete": True, "ok": all(child.get("ok") for child in last), "children": last, "startActions": actions}
        time.sleep(5)
    return {"complete": False, "ok": False, "children": last, "startActions": actions}


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


def child_ids_from_check_result(result):
    ids = []
    for child in (result or {}).get("children") or []:
        if child.get("jobId") and child.get("jobId") not in ids:
            ids.append(child.get("jobId"))
    return ids


def safe_identifier_part(value):
    text = re.sub(r"[^0-9A-Za-z]+", "_", str(value or "").strip().lower()).strip("_")
    return text or "x"


def compact_identifier(parts, max_length=63):
    text = "_".join(safe_identifier_part(part) for part in parts if part not in (None, ""))
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip("_")


def timestamp_tag():
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def write_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def clone_client(client):
    return ConsoleClient(
        client.base_url,
        cookie=client.cookie,
        timeout=client.timeout,
        csrf_token=client.csrf_token,
        retries=client.retries,
        extra_headers=dict(client.extra_headers),
    )


def effective_batch_size(pair_count, batch_size):
    value = int(batch_size or 0)
    if value <= 0:
        return max(int(pair_count or 0), 1)
    return value


def create_job_args(args, tables):
    explicit_tables = has_explicit_autotest_tables(args)
    return SimpleNamespace(
        source_ds_id=args.source_ds_id,
        target_ds_id=args.target_ds_id,
        source_type=args.source_type,
        target_type=args.target_type,
        source_host_type=args.source_host_type,
        target_host_type=args.target_host_type,
        mode=args.mode,
        job_type=None,
        job_name=args.job_name,
        desc=args.desc or "CloudCanal autotest",
        level=args.level,
        spec_id=args.spec_id,
        source_db=args.source_schema,
        source_schema=None,
        target_db=args.target_schema,
        target_schema=None,
        target_table=getattr(args, "target_table", None),
        table=(getattr(args, "table", None) or []) if explicit_tables else tables,
        table_map=getattr(args, "table_map", None) or [],
        column_map=getattr(args, "column_map", None) or [],
        source_schema_json=getattr(args, "source_schema_json", None),
        target_schema_json=getattr(args, "target_schema_json", None),
        mapping_json=getattr(args, "mapping_json", None),
        extra_json=args.extra_json,
        processor_config_json=getattr(args, "processor_config_json", None),
        source_charset=getattr(args, "source_charset", None),
        target_charset=getattr(args, "target_charset", None),
        table_rule=getattr(args, "table_rule", None),
        column_rule=getattr(args, "column_rule", None),
        table_mapping_method=getattr(args, "table_mapping_method", None),
        table_select_mode=args.table_select_mode,
        auto_create_target=True,
        struct_migration=args.struct_migration,
        auto_start=False,
        start_after_create=False,
        short_term_num=None,
        key_conflict_strategy=args.key_conflict_strategy,
        filter_ddl=args.filter_ddl,
        clean_target_before_full=args.clean_target_before_full,
        skip_precheck=args.skip_precheck,
        precheck_stage="final",
        precheck_only=False,
        ignore_precheck_fail=args.ignore_precheck_fail,
        dry_run=False,
        cluster_id=args.cluster_id,
        cluster_name_like=args.cluster_name_like,
        non_interactive=True,
    )


def create_autotest_job(args, client, source_type, target_type, source_adapter):
    tables = selected_autotest_tables(args, source_adapter)
    ns = create_job_args(args, tables)
    payload = build_datajob_payload(ns, client)
    source_schema = parse_json_field(payload.get("sourceSchema"), [])
    flags = table_auto_create_flags(source_schema)
    column_counts = table_column_counts(source_schema)
    missing_flags = [table for table in tables if not flags.get(table)]
    if missing_flags:
        raise ApiError("auto-create flag missing in sourceSchema for tables: " + ",".join(missing_flags))

    result = {
        "dryRun": bool(args.dry_run),
        "sourceType": source_type,
        "targetType": target_type,
        "profile": args.profile,
        "tables": tables,
        "targetAutoCreate": flags,
        "sourceColumnCounts": column_counts,
    }
    if args.dry_run:
        result["payload"] = mask_payload(payload)
        return result

    if not args.skip_precheck:
        items = precheck(client, "final", payload)
        failures = failed_prechecks(items if isinstance(items, list) else [])
        result["precheckItems"] = len(items) if isinstance(items, list) else 0
        result["precheckFailures"] = [precheck_title(item) for item in failures[:10]]
        if failures and not args.ignore_precheck_fail:
            raise ApiError("final precheck failed: " + "; ".join(result["precheckFailures"]))

    response = client.post_multipart(CREATE_JOB_PATH, {"dataJobData": json_part(payload)})
    job_id = client.ensure_success(response, "create autotest data job")
    created = wait_datajob_create_finished(client, job_id, args.start_timeout_seconds)
    result["createConsole"] = {
        "consoleJobId": created.get("consoleJobId"),
        "consoleTaskState": created.get("consoleTaskState"),
        "lifeCycleState": created.get("lifeCycleState"),
    }
    if args.start_after_create:
        result["startResult"] = continue_or_start_job(client, job_id, args.start_timeout_seconds)
    saved = query_job(client, job_id)
    schema = query_job_schema(client, job_id, source_type, target_type)
    result.update(
        {
            "jobId": job_id,
            "jobName": job_name(saved),
            "lifeCycleState": saved.get("lifeCycleState"),
            "taskState": saved.get("dataTaskState") or saved.get("currTaskStatus"),
            "schemaType": type(schema).__name__,
        }
    )
    return result


def add_check_child(client, job_id, dry_run=False):
    payload = {
        "jobId": parse_int(job_id, "jobId"),
        "checkOnce": True,
        "checkPeriod": False,
        "checkPeriodCronExpr": None,
        "fullCheck": True,
        "fullPeriod": False,
        "fullPeriodCronExpr": None,
    }
    if dry_run:
        return {"path": ADD_CHECK_CHILD_JOB_PATH, "payload": payload}
    response = client.post_json(ADD_CHECK_CHILD_JOB_PATH, payload)
    return client.ensure_success(response, "add check child job")


def common_adapter_kwargs(args, prefix):
    return {
        "user": getattr(args, prefix + "_user", None),
        "host_type": getattr(args, prefix + "_host_type", None),
        "host": getattr(args, prefix + "_host", None),
    }


def compare_kwargs(args):
    return {
        "source_user": args.source_user,
        "target_user": args.target_user,
        "source_host_type": args.source_host_type,
        "target_host_type": args.target_host_type,
        "source_host": args.source_host,
        "target_host": args.target_host,
        "check_mode": getattr(args, "local_check_mode", None) or getattr(args, "check_mode", None) or "count",
    }


def snapshots_equal(src, dst, check_mode):
    if check_mode == "digest":
        return src.get("exists") == dst.get("exists") and src.get("rows") == dst.get("rows") and src.get("digest") == dst.get("digest")
    return src.get("exists") == dst.get("exists") and src.get("rows") == dst.get("rows")


def compare_with_adapters(source_adapter, target_adapter, source_ds, target_ds, source_password, target_password, source_schema, target_schema, profile, allow_non_temp, tables=None, table_pairs=None, **kwargs):
    check_mode = kwargs.get("check_mode") or "count"
    if check_mode not in ("count", "digest"):
        raise ValueError("unsupported check mode: " + str(check_mode))
    selected_pairs = table_pairs or [(table, table) for table in (tables or source_adapter.profile_tables(profile))]
    result = {
        "sourceSchema": source_schema,
        "targetSchema": target_schema,
        "profile": profile,
        "checkMode": check_mode,
        "tables": [],
        "ignoredTables": [],
        "sourceAdapter": source_adapter.name,
        "targetAdapter": target_adapter.name,
        "ok": True,
    }
    for source_table, target_table in selected_pairs:
        src = source_adapter.table_snapshot(
            source_ds,
            source_password,
            source_schema,
            source_table,
            check_mode,
            allow_non_temp,
            user=kwargs.get("source_user"),
            host_type=kwargs.get("source_host_type"),
            host=kwargs.get("source_host"),
        )
        dst = target_adapter.table_snapshot(
            target_ds,
            target_password,
            target_schema,
            target_table,
            check_mode,
            allow_non_temp,
            user=kwargs.get("target_user"),
            host_type=kwargs.get("target_host_type"),
            host=kwargs.get("target_host"),
        )
        ok = snapshots_equal(src, dst, check_mode)
        table_result = {"table": source_table, "ok": ok, "source": src, "target": dst, "primaryKeyColumns": ["id"]}
        if target_table != source_table:
            table_result["targetTable"] = target_table
        result["tables"].append(table_result)
        if not ok:
            result["ok"] = False
    return result


def autotest_deps_cmd(_args, _client):
    print_json({"adapters": adapter_reports()})
    return 0


def autotest_install_deps_cmd(args, _client):
    commands = install_dependency_commands(args.adapter)
    if not commands:
        print_json({"adapter": args.adapter, "commands": [], "installed": False})
        return 0
    if not args.yes:
        print_json({"adapter": args.adapter, "commands": commands, "installed": False})
        return 0
    results = []
    for command in commands:
        proc = subprocess.run(shlex.split(command), text=True, capture_output=True)
        results.append(
            {
                "command": command,
                "returnCode": proc.returncode,
                "stdoutTail": proc.stdout[-2000:],
                "stderrTail": proc.stderr[-2000:],
            }
        )
        if proc.returncode != 0:
            print_json({"adapter": args.adapter, "commands": commands, "installed": False, "results": results})
            return proc.returncode
    print_json({"adapter": args.adapter, "commands": commands, "installed": True, "results": results})
    return 0


def autotest_plan_cmd(args, _client):
    data = {
        "mode": args.test_mode,
        "batchSize": args.batch_size,
        "outline": [{"category": c, "priority": p, "scope": s} for c, p, s in PLAN_OUTLINE],
        "devGate": [
            "one multi-table job per datasource pair/profile",
            "initialize temp source dataset",
            "prepare temp target namespace",
            "create full+increment+structure job",
            "start, full local/check-child validation, incremental-baseline local/check-child validation, faker CRUD, post-CUD validation, markdown report",
        ],
        "releaseGate": [
            "dev gate",
            "DDL cases",
            "subscription add/remove/remap cases",
            "position/reset/restart/replay ops",
            "check/revise inconsistency injection",
            "performance profiles",
        ],
        "mysqlDetailAutoCoverage": MYSQL_DETAIL_COVERAGE,
        "adapters": adapter_reports(),
        "rules": [
            "CloudCanal job may include many tables; do not create one task per table for the core profile.",
            "N*N execution is batched by pair count, default 5 pairs per batch.",
            "Datasource-specific behavior belongs in db_adapters, not in autotest orchestration.",
            "Special target PK, virtual column, filter, custom processor, and advanced subscription payloads must be frontend-trace verified before marked 1:1.",
        ],
    }
    print_json(data)
    return 0


class SelftestAdapter:
    name = "selftest-family"
    default_profile = "selftest-core"
    can_init_source = True
    can_prepare_target = True
    can_cleanup = True
    can_faker_crud = True
    can_compare = True

    def supports_source(self, _ds_type):
        return True

    def supports_target(self, _ds_type):
        return True

    def profile_tables_for_namespace(self, _profile, _namespace):
        return ["selftest_pk_1", "selftest_pk_2"]

    def init_source_dataset(self, *_args, **_kwargs):
        return {"ok": True, "tables": self.profile_tables_for_namespace(None, None), "seedRowsPerTable": 1000}

    def prepare_target_dataset(self, *_args, **_kwargs):
        return {"ok": True, "tables": self.profile_tables_for_namespace(None, None)}

    def faker_crud(self, *_args, **_kwargs):
        return {"ok": True, "changedRows": 1000, "stats": {"selftest_pk_1": {"insert": 1000}}}

    def table_snapshot(self, _ds, _password, _schema, _table, _check_mode, _allow_non_temp, **_kwargs):
        return {"exists": True, "rows": 1000}


def selftest_args(**overrides):
    data = {
        "test_mode": "dev",
        "source_ds_id": 10,
        "target_ds_id": 20,
        "source_type": None,
        "target_type": None,
        "source_schema": "cc_auto_selftest_src",
        "target_schema": "cc_auto_selftest_dst",
        "profile": None,
        "table": [],
        "table_map": [],
        "target_table": None,
        "dry_run": False,
        "skip_init": False,
        "rows": 1000,
        "allow_non_temp_schema": False,
        "source_password": "source-password",
        "target_password": "target-password",
        "wait_seconds": 0,
        "sql_check": True,
        "add_check_child": True,
        "crud_rounds": 1000,
        "seed": 20260612,
        "wait_after_crud_seconds": 0,
        "start_timeout_seconds": 1,
        "wait_increment_ready_seconds": 1,
        "wait_check_child_seconds": 1,
        "output_dir": None,
        "collect_stage_logs": False,
        "source_user": None,
        "source_host_type": None,
        "source_host": None,
        "target_user": None,
        "target_host_type": None,
        "target_host": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def selftest_check_child_result():
    return {
        "ok": True,
        "complete": True,
        "children": [
            {
                "jobId": 200,
                "complete": True,
                "ok": True,
                "tasks": [{"taskId": 300, "loss": 0, "diff": 0}],
            }
        ],
    }


def run_autotest_selftest_case(args):
    adapter = SelftestAdapter()
    patches = {
        "query_datasource": lambda _client, ds_id: {"id": ds_id, "dataSourceType": "MySQL"},
        "adapter_for_pair": lambda _source, _target: (adapter, adapter),
        "resolve_cluster_id": lambda _args, _client: None,
        "create_autotest_job": lambda *_args, **_kwargs: {"ok": True, "jobId": 100},
        "wait_full_complete": lambda *_args, **_kwargs: {"ok": True, "jobId": 100},
        "wait_increment_ready": lambda *_args, **_kwargs: {"ok": True, "jobId": 100},
        "add_check_child": lambda *_args, **_kwargs: {"ok": True, "jobId": 200},
        "wait_check_child": lambda *_args, **_kwargs: selftest_check_child_result(),
        "wait_check_jobs": lambda *_args, **_kwargs: selftest_check_child_result(),
        "job_action_result": lambda *_args, **_kwargs: {"ok": True},
    }
    originals = {name: globals()[name] for name in patches}
    original_sleep = time.sleep
    try:
        for name, value in patches.items():
            globals()[name] = value
        time.sleep = lambda _seconds: None
        return run_autotest_pair(args, object())
    finally:
        for name, value in originals.items():
            globals()[name] = value
        time.sleep = original_sleep


def assert_selftest(condition, message, failures):
    if not condition:
        failures.append(message)


def autotest_selftest_cmd(_args, _client):
    failures = []
    default_run = run_autotest_selftest_case(selftest_args())
    default_names = [step.get("name") for step in default_run.get("steps") or []]
    default_phases = [step.get("phase") for step in default_run.get("steps") or []]
    required_names = [
        "wait-full-complete",
        "full-local-count-check",
        "full-cloudcanal-check-add",
        "full-cloudcanal-check-result",
        "wait-increment-ready",
        "incremental-baseline-local-count-check",
        "incremental-baseline-cloudcanal-check-replay",
        "incremental-baseline-cloudcanal-check-result",
        "faker-crud",
        "incremental-local-count-check",
        "incremental-cloudcanal-check-replay",
        "incremental-cloudcanal-check-result",
    ]
    for name in required_names:
        assert_selftest(name in default_names, "missing default step " + name, failures)
    if not failures:
        assert_selftest(
            default_names.index("incremental-baseline-local-count-check")
            < default_names.index("faker-crud")
            < default_names.index("incremental-local-count-check"),
            "incremental baseline must run before faker CRUD and post-CUD local check",
            failures,
        )
    for phase in ("FULL_CHECK", "INCREMENT_BASELINE_VERIFY", "INCREMENT_BASELINE_CHECK", "INCREMENT_CHECK"):
        assert_selftest(phase in default_phases, "missing phase " + phase, failures)

    no_sql_run = run_autotest_selftest_case(selftest_args(sql_check=False, crud_rounds=0))
    no_sql_names = [step.get("name") for step in no_sql_run.get("steps") or []]
    assert_selftest("wait-full-complete" in no_sql_names, "--no-sql-check must still wait for full completion", failures)
    assert_selftest("full-cloudcanal-check-add" in no_sql_names, "--no-sql-check must still run CloudCanal check child when enabled", failures)
    assert_selftest(not any(str(name).startswith("full-local-") for name in no_sql_names), "--no-sql-check must skip local full checks", failures)

    wait_start_actions = []
    original_query_job = globals()["query_job"]
    original_active_fsm_job = globals()["active_fsm_job"]
    original_start_job = globals()["start_job"]
    try:
        globals()["query_job"] = lambda _client, _job_id: {
            "dataJobId": 200,
            "dataJobName": "selftest_check_child",
            "dataTaskState": "CHECK",
            "currTaskStatus": "WAIT_START",
            "fsmActive": True,
            "dataTasks": [{"dataTaskId": 300, "dataTaskType": "CHECK", "dataTaskStatus": "WAIT_START"}],
        }
        globals()["active_fsm_job"] = lambda _client, job_id: wait_start_actions.append(job_id) or {"ok": True}
        actions = ensure_check_jobs_running(object(), [200])
        assert_selftest(wait_start_actions == [], "WAIT_START check child must wait for scheduler instead of active-fsm", failures)
        assert_selftest(actions and actions[0].get("action") == "wait-start", "WAIT_START check child wait action must be recorded", failures)

        active_fsm_actions = []
        globals()["query_job"] = lambda _client, _job_id: {
            "dataJobId": 201,
            "dataJobName": "selftest_check_child_inactive",
            "dataTaskState": "INIT",
            "currTaskStatus": "INIT",
            "fsmActive": False,
            "dataTasks": [{"dataTaskId": 301, "dataTaskType": "CHECK", "dataTaskStatus": "INIT"}],
        }
        globals()["active_fsm_job"] = lambda _client, job_id: active_fsm_actions.append(job_id) or {"ok": True}
        actions = ensure_check_jobs_running(object(), [201])
        assert_selftest(active_fsm_actions == [201], "inactive INIT check child must use frontend-equivalent active-fsm", failures)
        assert_selftest(actions and actions[0].get("action") == "active-fsm", "inactive INIT check child action must be active-fsm", failures)

        start_actions = []
        globals()["query_job"] = lambda _client, _job_id: {
            "dataJobId": 202,
            "dataJobName": "selftest_check_child_active",
            "dataTaskState": "INIT",
            "currTaskStatus": "INIT",
            "fsmActive": True,
            "dataTasks": [{"dataTaskId": 302, "dataTaskType": "CHECK", "dataTaskStatus": "INIT"}],
        }
        globals()["start_job"] = lambda _client, job_id: start_actions.append(job_id) or {"ok": True}
        actions = ensure_check_jobs_running(object(), [202])
        assert_selftest(start_actions == [], "active INIT check child must wait for scheduler instead of start", failures)
        assert_selftest(actions and actions[0].get("action") == "wait-active-fsm", "active INIT check child wait action must be recorded", failures)
    finally:
        globals()["query_job"] = original_query_job
        globals()["active_fsm_job"] = original_active_fsm_job
        globals()["start_job"] = original_start_job

    lines = []
    append_run_diagnostics(
        lines,
        {
            "steps": default_run.get("steps", [])
            + [
                {
                    "name": "incremental-cloudcanal-check-logs",
                    "phase": "LOGS",
                    "ok": True,
                    "result": {
                        "path": "/tmp/cloudcanal-selftest-log.json",
                        "recordCount": 1,
                        "summary": {"categories": {"TASK_ERROR": 1}, "samples": ["ERROR selftest"]},
                    },
                }
            ]
        },
    )
    report_text = "\n".join(lines)
    for token in (
        "INCREMENT_BASELINE_VERIFY",
        "incremental-baseline-local-count-check",
        "incremental-baseline-cloudcanal-check-result",
        "stageLogs",
        "/tmp/cloudcanal-selftest-log.json",
    ):
        assert_selftest(token in report_text, "report diagnostics missing " + token, failures)

    output = {
        "ok": not failures,
        "checks": {
            "defaultFlowSteps": default_names,
            "defaultFlowPhases": default_phases,
            "noSqlCheckSteps": no_sql_names,
            "reportContainsStageLogs": "stageLogs" in report_text,
        },
        "failures": failures,
    }
    print_json(output)
    return 0 if output["ok"] else 2


def build_autotest_matrix(args, client):
    payload = read_json_arg(args.payload_json, {})
    payload.setdefault("pageSize", args.page_size)
    if args.life_cycle_state:
        payload["lifeCycleState"] = args.life_cycle_state
    response = client.post_json(LIST_BY_CONDITION_PATH, payload)
    items = client.ensure_success(response, "list datasources for autotest matrix") or []
    if args.desc_prefix:
        items = [item for item in items if str(item.get("instanceDesc") or "").startswith(args.desc_prefix)]
    exclude_types = set(normalize_ds_type(value) for value in (getattr(args, "exclude_type", None) or []) if value)
    if exclude_types:
        items = [item for item in items if normalize_ds_type(item.get("dataSourceType")) not in exclude_types]
    if args.source_type:
        source_filter = normalize_ds_type(args.source_type)
        sources = [item for item in items if normalize_ds_type(item.get("dataSourceType")) == source_filter]
    else:
        sources = items
    if args.source_desc_prefix:
        sources = [item for item in sources if str(item.get("instanceDesc") or "").startswith(args.source_desc_prefix)]
    if args.target_type:
        target_filter = normalize_ds_type(args.target_type)
        targets = [item for item in items if normalize_ds_type(item.get("dataSourceType")) == target_filter]
    else:
        targets = items
    if args.target_desc_prefix:
        targets = [item for item in targets if str(item.get("instanceDesc") or "").startswith(args.target_desc_prefix)]

    pairs = []
    for source in sources:
        for target in targets:
            if not args.include_same and int(source.get("id")) == int(target.get("id")):
                continue
            source_type = normalize_ds_type(source.get("dataSourceType"))
            target_type = normalize_ds_type(target.get("dataSourceType"))
            try:
                source_adapter, target_adapter = adapter_for_pair(source_type, target_type)
                supported = True
                unsupported_reason = None
                can_init_source = bool(source_adapter.can_init_source and source_adapter.supports_source(source_type))
                can_prepare_target = bool(target_adapter.can_prepare_target and target_adapter.supports_target(target_type))
                can_faker_crud = bool(source_adapter.can_faker_crud and source_adapter.supports_source(source_type))
                can_compare = bool(
                    source_adapter.can_compare
                    and target_adapter.can_compare
                    and source_adapter.supports_source(source_type)
                    and target_adapter.supports_target(target_type)
                )
            except Exception as e:
                source_adapter = None
                target_adapter = None
                supported = False
                unsupported_reason = str(e)
                can_init_source = False
                can_prepare_target = False
                can_faker_crud = False
                can_compare = False
            pairs.append(
                {
                    "sourceDataSourceId": source.get("id"),
                    "targetDataSourceId": target.get("id"),
                    "sourceType": source_type,
                    "targetType": target_type,
                    "sourceDesc": source.get("instanceDesc"),
                    "targetDesc": target.get("instanceDesc"),
                    "sourceAdapter": source_adapter.name if source_adapter else None,
                    "targetAdapter": target_adapter.name if target_adapter else None,
                    "sourceDataModel": source_adapter.data_model if source_adapter else None,
                    "targetDataModel": target_adapter.data_model if target_adapter else None,
                    "canInitSource": can_init_source,
                    "canPrepareTarget": can_prepare_target,
                    "canFakerCrud": can_faker_crud,
                    "canCompare": can_compare,
                    "fullDataVerificationReady": bool(
                        source_adapter and target_adapter and can_init_source and can_prepare_target and can_faker_crud and can_compare
                    ),
                    "adapterRouted": supported,
                    "unsupportedReason": unsupported_reason,
                }
            )
    if args.ready_only:
        pairs = [pair for pair in pairs if pair.get("fullDataVerificationReady")]
    batch_size = effective_batch_size(len(pairs), args.batch_size)
    batches = [pairs[i : i + batch_size] for i in range(0, len(pairs), batch_size)]
    by_pair_type = {}
    for pair in pairs:
        key = pair["sourceType"] + "->" + pair["targetType"]
        by_pair_type[key] = by_pair_type.get(key, 0) + 1
    selected_batches = batches
    if args.batch_no:
        if args.batch_no < 1 or args.batch_no > len(batches):
            selected_batches = []
        else:
            selected_batches = [batches[args.batch_no - 1]]
    output = {
        "datasourceCount": len(items),
        "sourceCount": len(sources),
        "targetCount": len(targets),
        "pairCount": len(pairs),
        "fullDataVerificationReadyPairCount": len([pair for pair in pairs if pair.get("fullDataVerificationReady")]),
        "batchSize": batch_size,
        "requestedBatchSize": args.batch_size,
        "batchCount": len(batches),
        "batchNo": args.batch_no,
        "pairTypes": by_pair_type,
    }
    if not args.summary_only:
        if args.batch_no:
            output["batches"] = [{"batchNo": args.batch_no, "pairs": selected_batches[0] if selected_batches else []}]
        else:
            output["batches"] = [{"batchNo": i + 1, "pairs": batch} for i, batch in enumerate(selected_batches)]
    return output


def autotest_matrix_cmd(args, client):
    output = build_autotest_matrix(args, client)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(args.output)
    else:
        print_json(output)
    return 0


def autotest_init_cmd(args, client):
    ds = query_datasource(client, parse_int(args.data_source_id, "dataSourceId"))
    ds_type = normalize_ds_type(args.data_source_type or ds.get("dataSourceType") or ds.get("type"))
    adapter = adapter_for_type(ds_type)
    result = adapter.init_source_dataset(
        ds,
        args.password,
        args.schema,
        args.rows,
        args.profile or adapter.default_profile,
        args.drop_existing,
        args.allow_non_temp_schema,
        **common_adapter_kwargs(args, "source"),
    )
    print_json(result)
    return 0


def autotest_prepare_target_cmd(args, client):
    ds = query_datasource(client, parse_int(args.data_source_id, "dataSourceId"))
    ds_type = normalize_ds_type(args.data_source_type or ds.get("dataSourceType") or ds.get("type"))
    adapter = adapter_for_type(ds_type)
    result = adapter.prepare_target_dataset(
        ds,
        args.password,
        args.schema,
        args.drop_existing,
        args.allow_non_temp_schema,
        **common_adapter_kwargs(args, "target"),
    )
    print_json(result)
    return 0 if result.get("ok", True) else 2


def autotest_cleanup_cmd(args, client):
    ds = query_datasource(client, parse_int(args.data_source_id, "dataSourceId"))
    ds_type = normalize_ds_type(args.data_source_type or ds.get("dataSourceType") or ds.get("type"))
    adapter = adapter_for_type(ds_type)
    result = adapter.cleanup_dataset(
        ds,
        args.password,
        args.schema,
        args.allow_non_temp_schema,
        user=args.user,
        host_type=args.host_type,
        host=args.host,
    )
    print_json(result)
    return 0


def autotest_crud_cmd(args, client):
    ds = query_datasource(client, parse_int(args.data_source_id, "dataSourceId"))
    ds_type = normalize_ds_type(args.data_source_type or ds.get("dataSourceType") or ds.get("type"))
    adapter = adapter_for_type(ds_type)
    result = adapter.faker_crud(
        ds,
        args.password,
        args.schema,
        args.rounds,
        args.profile or adapter.default_profile,
        args.seed,
        args.allow_non_temp_schema,
        **common_adapter_kwargs(args, "source"),
    )
    print_json(result)
    return 0 if result.get("ok", True) else 2


def autotest_check_cmd(args, client):
    source_ds = query_datasource(client, parse_int(args.source_ds_id, "sourceDataSourceId"))
    target_ds = query_datasource(client, parse_int(args.target_ds_id, "targetDataSourceId"))
    source_type = normalize_ds_type(args.source_type or source_ds.get("dataSourceType") or source_ds.get("type"))
    target_type = normalize_ds_type(args.target_type or target_ds.get("dataSourceType") or target_ds.get("type"))
    source_adapter, target_adapter = adapter_for_pair(source_type, target_type)
    args.profile = args.profile or source_adapter.default_profile
    tables = selected_autotest_tables(args, source_adapter)
    table_pairs = selected_autotest_table_pairs(args, source_adapter)
    local_compare_kwargs = compare_kwargs(args)
    result = compare_with_adapters(
        source_adapter,
        target_adapter,
        source_ds,
        target_ds,
        args.source_password,
        args.target_password,
        args.source_schema,
        args.target_schema,
        args.profile,
        args.allow_non_temp_schema,
        tables=tables,
        table_pairs=table_pairs,
        **local_compare_kwargs,
    )
    print_json(result)
    return 0 if result["ok"] else 2


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


def record_step(run, name, result, phase=None, ok=None):
    if ok is None:
        ok = bool(result.get("ok")) if isinstance(result, dict) and "ok" in result else True
    step = {"name": name, "ok": bool(ok), "result": result}
    if phase:
        step["phase"] = phase
    run["steps"].append(step)
    return result


def record_error_step(run, name, error, phase):
    run["steps"].append({"name": name, "ok": False, "phase": phase, "error": str(error)})


def mark_run_failed(run, phase, error=None):
    run["ok"] = False
    run.setdefault("failurePhase", phase)
    if error is not None:
        run.setdefault("error", str(error))


def adapter_readiness_errors(args, source_type, target_type, source_adapter, target_adapter, explicit_tables):
    errors = []
    if not source_adapter.supports_source(source_type):
        errors.append(
            {
                "side": "source",
                "type": source_type,
                "adapter": source_adapter.name,
                "capability": "sourceDataType",
                "message": "adapter is routed but not supported as an autotest source",
            }
        )
    if not target_adapter.supports_target(target_type):
        errors.append(
            {
                "side": "target",
                "type": target_type,
                "adapter": target_adapter.name,
                "capability": "targetDataType",
                "message": "adapter is routed but not supported as an autotest target",
            }
        )
    if getattr(args, "dry_run", False):
        return errors
    if not getattr(args, "skip_init", False) and not explicit_tables:
        if not source_adapter.can_init_source:
            errors.append({"side": "source", "type": source_type, "adapter": source_adapter.name, "capability": "initSource"})
        if not target_adapter.can_prepare_target:
            errors.append({"side": "target", "type": target_type, "adapter": target_adapter.name, "capability": "prepareTarget"})
    if getattr(args, "crud_rounds", 0) and not explicit_tables and not source_adapter.can_faker_crud:
        errors.append({"side": "source", "type": source_type, "adapter": source_adapter.name, "capability": "fakerCrud"})
    if getattr(args, "sql_check", False):
        if not source_adapter.can_compare:
            errors.append({"side": "source", "type": source_type, "adapter": source_adapter.name, "capability": "compare"})
        if not target_adapter.can_compare:
            errors.append({"side": "target", "type": target_type, "adapter": target_adapter.name, "capability": "compare"})
    return errors


def cloudcanal_check_phase(stage_name):
    if stage_name == "full":
        return "FULL_CHECK"
    if stage_name == "incremental-baseline":
        return "INCREMENT_BASELINE_CHECK"
    if stage_name == "incremental":
        return "INCREMENT_CHECK"
    return "CHECK"


def run_cloudcanal_check(run, args, client, job_id, stage_name, existing_child_ids=None):
    if not args.add_check_child or args.dry_run or not job_id:
        return []
    child_ids = list(existing_child_ids or [])
    phase = cloudcanal_check_phase(stage_name)
    try:
        if child_ids:
            replay_results = []
            for child_id in child_ids:
                replay_results.append(job_action_result(client, "replay", child_id))
            record_step(run, stage_name + "-cloudcanal-check-replay", {"childJobIds": child_ids, "results": replay_results}, phase=phase)
            time.sleep(5)
            check_child = wait_check_jobs(client, child_ids, args.wait_check_child_seconds)
        else:
            record_step(run, stage_name + "-cloudcanal-check-add", add_check_child(client, job_id), phase=phase)
            check_child = wait_check_child(client, job_id, args.wait_check_child_seconds) if args.wait_check_child_seconds else {"complete": False, "ok": False, "children": []}
            child_ids = child_ids_from_check_result(check_child)
        record_step(run, stage_name + "-cloudcanal-check-result", check_child, phase=phase, ok=bool(check_child.get("ok")))
        if not check_child.get("ok"):
            mark_run_failed(run, "CHECK_CHILD_FAIL")
        return child_ids
    except Exception as e:
        record_error_step(run, stage_name + "-cloudcanal-check", e, phase)
        mark_run_failed(run, "CHECK_CHILD_FAIL", e)
        return child_ids


def maybe_collect_stage_logs(run, args, client, job_id, label, task_types=None):
    output_dir = getattr(args, "autotest_output_dir", None)
    pair_index = getattr(args, "pair_index", None)
    if not getattr(args, "collect_stage_logs", False) or not output_dir or not pair_index or not job_id or getattr(args, "dry_run", False):
        return None
    try:
        result = collect_stage_logs(
            client,
            query_job(client, job_id),
            output_dir,
            pair_index,
            label,
            task_types,
            include_warn=getattr(args, "include_warn_logs", False),
        )
        record_step(run, label + "-logs", result, phase="LOGS")
        return result
    except Exception as e:
        record_error_step(run, label + "-logs", e, "LOGS")
        return None


def run_autotest_pair(args, client):
    source_ds = query_datasource(client, parse_int(args.source_ds_id, "sourceDataSourceId"))
    target_ds = query_datasource(client, parse_int(args.target_ds_id, "targetDataSourceId"))
    source_type = normalize_ds_type(args.source_type or source_ds.get("dataSourceType") or source_ds.get("type"))
    target_type = normalize_ds_type(args.target_type or target_ds.get("dataSourceType") or target_ds.get("type"))
    source_adapter, target_adapter = adapter_for_pair(source_type, target_type)
    args.source_type = source_type
    args.target_type = target_type
    args.profile = args.profile or source_adapter.default_profile
    tables = selected_autotest_tables(args, source_adapter)
    table_pairs = selected_autotest_table_pairs(args, source_adapter)
    explicit_tables = has_explicit_autotest_tables(args)

    run = {
        "mode": args.test_mode,
        "sourceDataSourceId": int(args.source_ds_id),
        "targetDataSourceId": int(args.target_ds_id),
        "sourceType": source_type,
        "targetType": target_type,
        "sourceSchema": args.source_schema,
        "targetSchema": args.target_schema,
        "profile": args.profile,
        "tables": tables,
        "tablePairs": [{"source": source, "target": target} for source, target in table_pairs],
        "explicitTables": explicit_tables,
        "steps": [],
        "ok": True,
    }

    readiness_errors = adapter_readiness_errors(args, source_type, target_type, source_adapter, target_adapter, explicit_tables)
    if readiness_errors:
        record_step(
            run,
            "adapter-readiness",
            {
                "ok": False,
                "sourceAdapter": source_adapter.name,
                "targetAdapter": target_adapter.name,
                "errors": readiness_errors,
                "hint": "Use a READY adapter pair, or deliberately skip unsupported autotest stages.",
            },
            phase="INIT",
            ok=False,
        )
        mark_run_failed(run, "ADAPTER_NOT_READY")
        return run

    resolve_cluster_id(args, client)

    if not args.skip_init and args.dry_run:
        record_step(
            run,
            "init-source",
            {
                "dryRun": True,
                "schema": args.source_schema,
                "profile": args.profile,
                "tables": tables,
                "skipped": explicit_tables,
                "reason": "explicit user tables are assumed to already exist" if explicit_tables else None,
                "rows": args.rows,
            },
            phase="INIT",
        )
        record_step(
            run,
            "prepare-target",
            {
                "dryRun": True,
                "schema": args.target_schema,
                "skipped": explicit_tables,
                "reason": "explicit user tables do not use destructive target prepare by default" if explicit_tables else None,
            },
            phase="INIT",
        )
    elif not args.skip_init:
        if explicit_tables:
            record_step(
                run,
                "init-source",
                {
                    "skipped": True,
                    "schema": args.source_schema,
                    "tables": tables,
                    "reason": "explicit user tables are assumed to already exist",
                },
                phase="INIT",
            )
            record_step(
                run,
                "prepare-target",
                {
                    "skipped": True,
                    "schema": args.target_schema,
                    "tables": tables,
                    "reason": "explicit user tables do not use destructive target prepare by default",
                },
                phase="INIT",
            )
        else:
            try:
                record_step(
                    run,
                    "init-source",
                    source_adapter.init_source_dataset(
                        source_ds,
                        args.source_password,
                        args.source_schema,
                        args.rows,
                        args.profile,
                        True,
                        args.allow_non_temp_schema,
                        **common_adapter_kwargs(args, "source"),
                    ),
                    phase="INIT",
                )
            except Exception as e:
                record_error_step(run, "init-source", e, "INIT")
                mark_run_failed(run, "INIT_SOURCE_FAIL", e)
                return run
            try:
                record_step(
                    run,
                    "prepare-target",
                    target_adapter.prepare_target_dataset(
                        target_ds,
                        args.target_password,
                        args.target_schema,
                        True,
                        args.allow_non_temp_schema,
                        tables=tables,
                        **common_adapter_kwargs(args, "target"),
                    ),
                    phase="INIT",
                )
            except Exception as e:
                record_error_step(run, "prepare-target", e, "INIT")
                mark_run_failed(run, "PREPARE_TARGET_FAIL", e)
                return run
    try:
        job_result = create_autotest_job(args, client, source_type, target_type, source_adapter)
        record_step(run, "create-job", job_result, phase="CREATE")
    except Exception as e:
        record_error_step(run, "create-job", e, "CREATE")
        mark_run_failed(run, "CREATE_FAIL", e)
        return run

    if args.wait_seconds:
        time.sleep(args.wait_seconds)

    check_child_ids = []
    local_check_mode = getattr(args, "local_check_mode", "count") or "count"

    if (args.sql_check or args.add_check_child or args.crud_rounds) and not args.dry_run:
        try:
            record_step(
                run,
                "wait-full-complete",
                wait_full_complete(client, job_result["jobId"], args.start_timeout_seconds),
                phase="FULL",
            )
        except Exception as e:
            record_error_step(run, "wait-full-complete", e, "FULL")
            mark_run_failed(run, "FULL_FAIL", e)
            maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "full-failed", ("FULL",))
            return run
        maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "full-complete", ("FULL",))
        if args.sql_check:
            full_compare_kwargs = compare_kwargs(args)
            full_check = compare_with_adapters(
                source_adapter,
                target_adapter,
                source_ds,
                target_ds,
                args.source_password,
                args.target_password,
                args.source_schema,
                args.target_schema,
                args.profile,
                args.allow_non_temp_schema,
                tables=tables,
                table_pairs=table_pairs,
                **full_compare_kwargs,
            )
            record_step(run, "full-local-" + local_check_mode + "-check", full_check, phase="FULL_VERIFY")
            run["ok"] = run["ok"] and bool(full_check.get("ok"))
            if not full_check.get("ok"):
                mark_run_failed(run, "FULL_VERIFY_FAIL")
                check_child_ids = run_cloudcanal_check(run, args, client, job_result.get("jobId"), "full", check_child_ids)
                maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "full-cloudcanal-check", ("CHECK",))
                return run
        check_child_ids = run_cloudcanal_check(run, args, client, job_result.get("jobId"), "full", check_child_ids)
        maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "full-cloudcanal-check", ("CHECK",))
        if run.get("failurePhase"):
            return run

    if args.crud_rounds and not args.dry_run:
        try:
            record_step(
                run,
                "wait-increment-ready",
                wait_increment_ready(client, job_result["jobId"], args.wait_increment_ready_seconds),
                phase="INCREMENT_READY",
            )
        except Exception as e:
            record_error_step(run, "wait-increment-ready", e, "INCREMENT_READY")
            mark_run_failed(run, "INCREMENT_READY_FAIL", e)
            maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "increment-ready-failed", ("INCREMENT",))
            return run
        maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "increment-ready", ("INCREMENT",))

        if args.sql_check:
            baseline_compare_kwargs = compare_kwargs(args)
            baseline_check = compare_with_adapters(
                source_adapter,
                target_adapter,
                source_ds,
                target_ds,
                args.source_password,
                args.target_password,
                args.source_schema,
                args.target_schema,
                args.profile,
                args.allow_non_temp_schema,
                tables=tables,
                table_pairs=table_pairs,
                **baseline_compare_kwargs,
            )
            record_step(run, "incremental-baseline-local-" + local_check_mode + "-check", baseline_check, phase="INCREMENT_BASELINE_VERIFY")
            run["ok"] = run["ok"] and bool(baseline_check.get("ok"))
            if not baseline_check.get("ok"):
                mark_run_failed(run, "INCREMENT_BASELINE_VERIFY_FAIL")
                check_child_ids = run_cloudcanal_check(run, args, client, job_result.get("jobId"), "incremental-baseline", check_child_ids)
                maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "incremental-baseline-cloudcanal-check", ("INCREMENT", "CHECK"))
                return run
        check_child_ids = run_cloudcanal_check(run, args, client, job_result.get("jobId"), "incremental-baseline", check_child_ids)
        maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "incremental-baseline-cloudcanal-check", ("INCREMENT", "CHECK"))
        if run.get("failurePhase"):
            return run

        if explicit_tables:
            record_step(
                run,
                "faker-crud",
                {
                    "skipped": True,
                    "schema": args.source_schema,
                    "tables": tables,
                    "reason": "explicit user tables need a datasource-specific or user-provided mutator",
                },
                phase="FAKER",
            )
        else:
            try:
                record_step(
                    run,
                    "faker-crud",
                    source_adapter.faker_crud(
                        source_ds,
                        args.source_password,
                        args.source_schema,
                        args.crud_rounds,
                        args.profile,
                        args.seed,
                        args.allow_non_temp_schema,
                        **common_adapter_kwargs(args, "source"),
                    ),
                    phase="FAKER",
                )
            except Exception as e:
                record_error_step(run, "faker-crud", e, "FAKER")
                mark_run_failed(run, "FAKER_FAIL", e)
                check_child_ids = run_cloudcanal_check(run, args, client, job_result.get("jobId"), "incremental", check_child_ids)
                maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "incremental-after-faker-failed", ("INCREMENT", "CHECK"))
                return run
        if args.wait_after_crud_seconds:
            time.sleep(args.wait_after_crud_seconds)
        maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "incremental-after-crud", ("INCREMENT",))

        if args.sql_check:
            incr_compare_kwargs = compare_kwargs(args)
            incr_check = compare_with_adapters(
                source_adapter,
                target_adapter,
                source_ds,
                target_ds,
                args.source_password,
                args.target_password,
                args.source_schema,
                args.target_schema,
                args.profile,
                args.allow_non_temp_schema,
                tables=tables,
                table_pairs=table_pairs,
                **incr_compare_kwargs,
            )
            record_step(run, "incremental-local-" + local_check_mode + "-check", incr_check, phase="INCREMENT_VERIFY")
            run["ok"] = run["ok"] and bool(incr_check.get("ok"))
            if not incr_check.get("ok"):
                mark_run_failed(run, "INCREMENT_VERIFY_FAIL")
        check_child_ids = run_cloudcanal_check(run, args, client, job_result.get("jobId"), "incremental", check_child_ids)
        maybe_collect_stage_logs(run, args, client, job_result.get("jobId"), "incremental-cloudcanal-check", ("CHECK",))

    return run


def autotest_run_cmd(args, client):
    if getattr(args, "collect_stage_logs", False) and not getattr(args, "dry_run", False):
        output_dir = getattr(args, "output_dir", None) or os.path.join("/tmp", "cloudcanal-autotest-single-" + safe_identifier_part(timestamp_tag()))
        os.makedirs(output_dir, exist_ok=True)
        args.autotest_output_dir = output_dir
        args.pair_index = getattr(args, "pair_index", None) or 1
    run = run_autotest_pair(args, client)
    if getattr(args, "autotest_output_dir", None):
        run["outputDir"] = args.autotest_output_dir
    print_json(run)
    return 0 if run["ok"] else 2


def normalize_credential_entry(value):
    if value is None:
        return {}
    if isinstance(value, str):
        return {"password": value}
    if isinstance(value, dict):
        return value
    raise ValueError("invalid credential entry: " + str(value))


def credential_for(credentials, side, ds_id, ds_type):
    if not credentials:
        return {}
    candidates = []
    if isinstance(credentials.get(side), dict):
        candidates.append(credentials.get(side))
    if isinstance(credentials.get("datasources"), dict):
        candidates.append(credentials.get("datasources"))
    candidates.append(credentials)
    for container in candidates:
        if str(ds_id) in container:
            return normalize_credential_entry(container[str(ds_id)])
    defaults = credentials.get("defaults") if isinstance(credentials.get("defaults"), dict) else {}
    for key in (ds_type, str(ds_type).lower(), "*"):
        if key in defaults:
            return normalize_credential_entry(defaults[key])
    return {}


def credential_value(entry, *names, allow_empty=False):
    for name in names:
        if name in entry and entry[name] is not None and (allow_empty or entry[name] != ""):
            return entry[name]
    return None


def selected_pairs_from_matrix(matrix, batch_no=None, all_batches=False):
    if "batches" not in matrix:
        return matrix.get("pairs") or [], matrix.get("batchNo")
    batches = matrix.get("batches") or []
    if all_batches:
        pairs = []
        for batch in batches:
            pairs.extend(batch.get("pairs") or [])
        return pairs, "all"
    wanted = batch_no or matrix.get("batchNo")
    if wanted:
        for batch in batches:
            if int(batch.get("batchNo") or 0) == int(wanted):
                return batch.get("pairs") or [], batch.get("batchNo")
        return [], wanted
    if batches:
        return batches[0].get("pairs") or [], batches[0].get("batchNo")
    return [], wanted


def filter_pairs_for_args(pairs, args):
    exclude_types = set(normalize_ds_type(value) for value in (getattr(args, "exclude_type", None) or []) if value)
    if not exclude_types:
        return list(pairs or [])
    return [
        pair
        for pair in pairs or []
        if normalize_ds_type(pair.get("sourceType")) not in exclude_types and normalize_ds_type(pair.get("targetType")) not in exclude_types
    ]


def batch_pair_args(args, pair, pair_index, run_id, credentials):
    source_id = pair.get("sourceDataSourceId")
    target_id = pair.get("targetDataSourceId")
    source_type = pair.get("sourceType")
    target_type = pair.get("targetType")
    source_cred = credential_for(credentials, "source", source_id, source_type)
    target_cred = credential_for(credentials, "target", target_id, target_type)
    source_password = credential_value(source_cred, "password", "passwd", allow_empty=True)
    if source_password is None:
        source_password = args.source_password if args.source_password is not None else args.password
    target_password = credential_value(target_cred, "password", "passwd", allow_empty=True)
    if target_password is None:
        target_password = args.target_password if args.target_password is not None else args.password
    if source_password is None:
        raise ApiError("missing source password for datasource " + str(source_id))
    if target_password is None:
        raise ApiError("missing target password for datasource " + str(target_id))

    source_schema = compact_identifier([args.schema_prefix, run_id, "b" + str(args.batch_no or 1), "p" + str(pair_index), "s" + str(source_id), "src"])
    target_schema = compact_identifier([args.schema_prefix, run_id, "b" + str(args.batch_no or 1), "p" + str(pair_index), "t" + str(target_id), "dst"])
    job_name_value = compact_identifier([args.job_prefix, run_id, "b" + str(args.batch_no or 1), "p" + str(pair_index), source_id, target_id], max_length=64)

    return SimpleNamespace(
        base_url=args.base_url,
        cookie=args.cookie,
        cookie_file=args.cookie_file,
        csrf_token=args.csrf_token,
        header=args.header,
        timeout=args.timeout,
        cluster_id=args.cluster_id,
        cluster_name_like=args.cluster_name_like,
        test_mode=args.test_mode,
        source_ds_id=source_id,
        target_ds_id=target_id,
        source_type=source_type,
        target_type=target_type,
        source_schema=source_schema,
        target_schema=target_schema,
        source_password=source_password,
        target_password=target_password,
        profile=args.profile,
        rows=args.rows,
        mode=args.mode,
        job_name=job_name_value,
        desc=args.desc or "CloudCanal autotest batch " + run_id,
        level=args.level,
        spec_id=args.spec_id,
        extra_json=args.extra_json,
        table_select_mode=args.table_select_mode,
        target_table=getattr(args, "target_table", None),
        table=getattr(args, "table", []),
        table_map=getattr(args, "table_map", []),
        column_map=getattr(args, "column_map", []),
        source_schema_json=getattr(args, "source_schema_json", None),
        target_schema_json=getattr(args, "target_schema_json", None),
        mapping_json=getattr(args, "mapping_json", None),
        processor_config_json=getattr(args, "processor_config_json", None),
        source_charset=getattr(args, "source_charset", None),
        target_charset=getattr(args, "target_charset", None),
        table_rule=getattr(args, "table_rule", None),
        column_rule=getattr(args, "column_rule", None),
        table_mapping_method=getattr(args, "table_mapping_method", None),
        struct_migration=args.struct_migration,
        key_conflict_strategy=args.key_conflict_strategy,
        filter_ddl=args.filter_ddl,
        clean_target_before_full=args.clean_target_before_full,
        skip_init=args.skip_init,
        skip_precheck=args.skip_precheck,
        ignore_precheck_fail=args.ignore_precheck_fail,
        start_after_create=not args.no_start_after_create,
        start_timeout_seconds=args.start_timeout_seconds,
        wait_seconds=args.wait_seconds,
        wait_increment_ready_seconds=args.wait_increment_ready_seconds,
        crud_rounds=args.crud_rounds,
        seed=args.seed + pair_index,
        wait_after_crud_seconds=args.wait_after_crud_seconds,
        sql_check=not args.no_sql_check,
        local_check_mode=args.local_check_mode,
        add_check_child=not args.no_add_check_child,
        wait_check_child_seconds=args.wait_check_child_seconds,
        collect_stage_logs=not args.no_collect_stage_logs,
        include_warn_logs=getattr(args, "include_warn_logs", False),
        autotest_output_dir=getattr(args, "output_dir", None),
        pair_index=pair_index,
        allow_non_temp_schema=False,
        dry_run=args.dry_run,
        source_user=credential_value(source_cred, "user", "username") or args.source_user,
        source_host=credential_value(source_cred, "host") or args.source_host,
        source_host_type=credential_value(source_cred, "hostType", "host_type") or args.source_host_type,
        target_user=credential_value(target_cred, "user", "username") or args.target_user,
        target_host=credential_value(target_cred, "host") or args.target_host,
        target_host_type=credential_value(target_cred, "hostType", "host_type") or args.target_host_type,
    )


def step_result(run, name):
    for step in run.get("steps") or []:
        if step.get("name") == name:
            return step.get("result")
    return None


def run_job_id(run):
    result = step_result(run, "create-job") or {}
    return result.get("jobId")


def run_child_job_ids(run):
    ids = []
    for step in run.get("steps") or []:
        if not str(step.get("name") or "").endswith("-cloudcanal-check-result"):
            continue
        result = step.get("result") or {}
        for child in result.get("children") or []:
            if child.get("jobId") and child.get("jobId") not in ids:
                ids.append(child.get("jobId"))
    return ids


def job_ids_from_error(error):
    text = str(error or "")
    patterns = [
        r'"jobId"\s*:\s*(\d+)',
        r'"dataJobId"\s*:\s*(\d+)',
        r"dataJobId[=:]\s*(\d+)",
        r"DataJob's\s*\((\d+)\)",
        r"jobId[=:]\s*(\d+)",
    ]
    ids = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            value = int(match)
            if value not in ids:
                ids.append(value)
    return ids


def apply_job_context(item, job):
    if not job:
        return
    item["jobId"] = job.get("dataJobId")
    if job.get("consoleJobId"):
        item["consoleJobId"] = job.get("consoleJobId")
        item["consoleTaskState"] = job.get("consoleTaskState")
    child_ids = []
    for child in job.get("childJobs") or []:
        if child.get("dataJobId"):
            child_ids.append(child.get("dataJobId"))
    if child_ids:
        item["childJobIds"] = child_ids


def fill_error_context(client, item, error, output_dir):
    for job_id in job_ids_from_error(error):
        try:
            job = query_job(client, job_id)
        except Exception:
            continue
        apply_job_context(item, job)
        if item.get("jobId") and item.get("consoleTaskState") == "FAILED" and item.get("consoleJobId"):
            try:
                item["consoleFailure"] = console_job_failure_summary(query_console_job(client, item["consoleJobId"]))
            except Exception as e:
                item["consoleFailure"] = {"error": str(e)}
        if item.get("jobId") and item.get("status") != "PASS":
            try:
                item["failureLogs"] = collect_task_logs(client, job, output_dir, item.get("pairIndex"))
            except Exception as e:
                item["failureLogs"] = {"error": str(e)}
        return


def command_context():
    return {
        "script": 'python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py"',
        "base": '--base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE"',
    }


def followup_commands(item):
    pair = item.get("pair") or {}
    ctx = command_context()
    commands = []
    if item.get("jobId"):
        commands.append(ctx["script"] + " delete-job " + ctx["base"] + " --job-id " + str(item.get("jobId")))
        commands.append(ctx["script"] + " query-job " + ctx["base"] + " --job-id " + str(item.get("jobId")))
        commands.append(ctx["script"] + " tail-task-log " + ctx["base"] + " --job-id " + str(item.get("jobId")) + " --task-type INCREMENT --contains ERROR --text")
    for child_id in item.get("childJobIds") or []:
        commands.append(ctx["script"] + " delete-job " + ctx["base"] + " --job-id " + str(child_id))
    if item.get("sourceSchema"):
        commands.append(
            ctx["script"]
            + " autotest-cleanup-dataset "
            + ctx["base"]
            + " --data-source-id "
            + str(pair.get("sourceDataSourceId"))
            + " --schema "
            + str(item.get("sourceSchema"))
            + ' --password "$SOURCE_PASSWORD"'
        )
    if item.get("targetSchema"):
        commands.append(
            ctx["script"]
            + " autotest-cleanup-dataset "
            + ctx["base"]
            + " --data-source-id "
            + str(pair.get("targetDataSourceId"))
            + " --schema "
            + str(item.get("targetSchema"))
            + ' --password "$TARGET_PASSWORD"'
        )
    return commands


def matching_log_lines(content, include_warn=False):
    result = []
    for line in str(content or "").splitlines():
        if is_interesting_log_line(line, include_warn=include_warn):
            result.append(line)
    return result


def log_line_level(line):
    text = str(line or "")
    if "] ERROR" in text or " ERROR " in text:
        return "ERROR"
    if "] WARN" in text or " WARN " in text:
        return "WARN"
    return None


def is_interesting_log_line(line, include_warn=False):
    text = str(line or "")
    lower = text.lower()
    level = log_line_level(text)
    if level == "WARN":
        return bool(include_warn)
    if level == "ERROR":
        return True
    precise_needles = (
        "exception",
        "caused by:",
        "connection reset",
        "unexpectedly lost",
        "can not read response",
        "try to exist",
        "duplicate entry",
        "duplicate key",
    )
    if any(needle in lower for needle in precise_needles):
        return True
    # Check logs may report loss/diff in plain text; keep this narrow to avoid
    # matching arbitrary words in normal INFO lines.
    if re.search(r"\b(loss|diff)\s*[:=]\s*[1-9]", lower):
        return True
    return False


def tail_lines(content, limit=20):
    lines = str(content or "").splitlines()
    return lines[-limit:]


def abbreviate_text(value, max_length=500):
    text = str(value or "")
    if len(text) <= max_length:
        return text
    return text[:max_length] + "...(truncated,length=" + str(len(text)) + ")"


def summarize_log_records(records):
    categories = []
    samples = []
    task_types = []
    for record in records or []:
        task_type = record.get("taskType")
        if task_type and task_type not in task_types:
            task_types.append(task_type)
        for line in record.get("lines") or []:
            lower = line.lower()
            level = log_line_level(line)
            if any(token in lower for token in ("connection reset", "unexpectedly lost", "can not read response", "eofexception", "broken pipe")):
                category = "CONNECTION_CLOSED_DURING_TASK"
            elif level and ("timeout" in lower or "timed out" in lower):
                category = "TIMEOUT"
            elif "duplicate entry" in lower or "duplicate key" in lower:
                category = "DUPLICATE_KEY"
            elif re.search(r"\b(loss|diff)\s*[:=]\s*[1-9]", lower):
                category = "CHECK_LOSS_DIFF"
            elif level == "WARN":
                category = "TASK_WARN"
            elif level == "ERROR" or "exception" in lower:
                category = "TASK_ERROR"
            else:
                category = "MATCHED"
            if category not in categories:
                categories.append(category)
            if len(samples) < 8:
                samples.append(abbreviate_text(line, 360))
    return {"categories": categories, "taskTypes": task_types, "samples": samples}


def collect_stage_logs(client, job, output_dir, pair_index, label, task_types=None, include_warn=False):
    wanted = set(task_type_value(value) for value in (task_types or []) if value)
    records = []
    jobs = [job] + list(job.get("childJobs") or [])
    for current_job in jobs:
        job_id = current_job.get("dataJobId")
        for task in current_job.get("dataTasks") or []:
            task_type = task_type_value(task.get("dataTaskType"))
            if wanted and task_type not in wanted:
                continue
            task_id = task.get("dataTaskId")
            if not job_id or not task_id:
                continue
            payload = {"taskId": task_id, "dataJobId": job_id, "endRow": 0}
            try:
                logs = client.ensure_success(client.post_json(TAIL_TASK_LOG_PATH, payload), "tail task log") or []
            except Exception as e:
                records.append({"jobId": job_id, "taskId": task_id, "taskType": task_type, "error": str(e)})
                continue
            for log_file in logs:
                content = log_file.get("content") or ""
                interesting = matching_log_lines(content, include_warn=include_warn)
                if not interesting and not content:
                    continue
                records.append(
                    {
                        "jobId": job_id,
                        "taskId": task_id,
                        "taskType": task_type,
                        "fileName": log_file.get("fileName"),
                        "path": log_file.get("path"),
                        "endRow": log_file.get("endRow"),
                        "interestingLines": interesting[:80],
                        "tailLines": tail_lines(content, 8),
                    }
                )
    path = os.path.join(output_dir, "pair-" + str(pair_index) + "-" + safe_identifier_part(label) + "-logs.json")
    write_json_file(path, records)
    interesting_records = []
    for record in records:
        lines = record.get("interestingLines") or []
        if lines:
            interesting_records.append(
                {
                    "taskType": record.get("taskType"),
                    "fileName": record.get("fileName"),
                    "path": record.get("path"),
                    "lines": lines,
                }
            )
    return {
        "path": path,
        "recordCount": len(records),
        "interestingRecordCount": len(interesting_records),
        "summary": summarize_log_records(interesting_records),
    }


def collect_task_logs(client, job, output_dir, pair_index, include_warn=False):
    records = []
    jobs = [job] + list(job.get("childJobs") or [])
    for current_job in jobs:
        job_id = current_job.get("dataJobId")
        for task in current_job.get("dataTasks") or []:
            task_id = task.get("dataTaskId")
            if not job_id or not task_id:
                continue
            payload = {"taskId": task_id, "dataJobId": job_id, "endRow": 0}
            try:
                logs = client.ensure_success(client.post_json(TAIL_TASK_LOG_PATH, payload), "tail task log") or []
            except Exception as e:
                records.append({"jobId": job_id, "taskId": task_id, "error": str(e)})
                continue
            for log_file in logs:
                lines = matching_log_lines(log_file.get("content"), include_warn=include_warn)
                if lines:
                    records.append(
                        {
                            "jobId": job_id,
                            "taskId": task_id,
                            "taskType": task.get("dataTaskType"),
                            "fileName": log_file.get("fileName"),
                            "path": log_file.get("path"),
                            "lines": lines[:200],
                        }
                    )
    path = os.path.join(output_dir, "pair-" + str(pair_index) + "-failure-logs.json")
    write_json_file(path, records)
    return {"path": path, "recordCount": len(records), "summary": summarize_log_records(records)}


def job_needs_isolation(job):
    if not job:
        return False
    if job.get("lifeCycleState") in ("DELETED", "DELETE", "FINISH"):
        return False
    if job.get("currTaskStatus") in ("STOP", "COMPLETE", "FINISH"):
        return False
    return any(
        task.get("dataTaskStatus") in ("RUNNING", "WAIT_START", "WAIT_STOP", "INIT")
        for task in job.get("dataTasks") or []
    )


def wait_job_isolated(client, job_id, timeout_seconds=120):
    deadline = time.time() + max(int(timeout_seconds or 0), 1)
    last = None
    while time.time() < deadline:
        job = query_job(client, job_id)
        last = job_brief(job)
        if not job_needs_isolation(job):
            return {"isolated": True, "job": last}
        time.sleep(3)
    return {"isolated": False, "job": last}


def isolate_failed_job(client, job_id, timeout_seconds=120):
    job = query_job(client, job_id)
    before = job_brief(job)
    if not job_needs_isolation(job):
        return {"attempted": False, "reason": "job not running", "before": before}
    result = job_action_result(client, "stop", job_id)
    after = wait_job_isolated(client, job_id, timeout_seconds)
    return {"attempted": True, "action": "stop", "result": result, "before": before, "after": after}


def cleanup_batch_pair(client, pair_args):
    source_ds = query_datasource(client, parse_int(pair_args.source_ds_id, "sourceDataSourceId"))
    target_ds = query_datasource(client, parse_int(pair_args.target_ds_id, "targetDataSourceId"))
    source_adapter = adapter_for_type(pair_args.source_type)
    target_adapter = adapter_for_type(pair_args.target_type)
    return {
        "source": source_adapter.cleanup_dataset(
            source_ds,
            pair_args.source_password,
            pair_args.source_schema,
            False,
            **common_adapter_kwargs(pair_args, "source"),
        ),
        "target": target_adapter.cleanup_dataset(
            target_ds,
            pair_args.target_password,
            pair_args.target_schema,
            False,
            **common_adapter_kwargs(pair_args, "target"),
        ),
    }


def maybe_isolate_item(args, client, item):
    if getattr(args, "no_stop_failed_job", False) or not item.get("jobId"):
        return
    try:
        item["isolation"] = isolate_failed_job(client, item["jobId"], getattr(args, "stop_timeout_seconds", 120))
    except Exception as e:
        item["isolation"] = {"error": str(e)}


PHASE_ORDER = {
    "INIT": 10,
    "CREATE": 20,
    "FULL": 30,
    "FULL_VERIFY": 40,
    "FULL_CHECK": 50,
    "CHECK": 55,
    "INCREMENT_READY": 60,
    "INCREMENT_BASELINE_VERIFY": 65,
    "INCREMENT_BASELINE_CHECK": 68,
    "FAKER": 70,
    "INCREMENT_VERIFY": 80,
    "INCREMENT_CHECK": 85,
    "LOGS": 90,
}


def step_state(step):
    if step.get("error"):
        return "ERROR"
    if step.get("ok") is False:
        return "FAIL"
    return "PASS"


def summarize_run_phases(run):
    phases = {}
    for step in run.get("steps") or []:
        phase = step.get("phase") or "OTHER"
        row = phases.setdefault(phase, {"phase": phase, "steps": 0, "failed": 0, "errors": 0, "names": []})
        row["steps"] += 1
        if len(row["names"]) < 6:
            row["names"].append(step.get("name"))
        state = step_state(step)
        if state == "ERROR":
            row["errors"] += 1
        elif state == "FAIL":
            row["failed"] += 1
    result = []
    for row in phases.values():
        if row["errors"]:
            row["status"] = "ERROR"
        elif row["failed"]:
            row["status"] = "FAIL"
        else:
            row["status"] = "PASS"
        result.append(row)
    return sorted(result, key=lambda row: (PHASE_ORDER.get(row["phase"], 999), row["phase"]))


def summarize_local_checks(run):
    checks = []
    for step in run.get("steps") or []:
        result = step.get("result")
        if not isinstance(result, dict) or "tables" not in result or "checkMode" not in result:
            continue
        tables = [table for table in result.get("tables") or [] if isinstance(table, dict)]
        bad = [table for table in tables if not table.get("ok", True)]
        mismatches = []
        for table in bad[:6]:
            source = table.get("source") or {}
            target = table.get("target") or {}
            mismatches.append(
                {
                    "table": table.get("table"),
                    "targetTable": table.get("targetTable"),
                    "sourceRows": source.get("rows"),
                    "targetRows": target.get("rows"),
                    "sourceExists": source.get("exists"),
                    "targetExists": target.get("exists"),
                    "sourceDigest": source.get("digest"),
                    "targetDigest": target.get("digest"),
                }
            )
        checks.append(
            {
                "name": step.get("name"),
                "phase": step.get("phase"),
                "ok": bool(result.get("ok")),
                "checkMode": result.get("checkMode"),
                "tableCount": len(tables),
                "mismatchCount": len(bad),
                "mismatches": mismatches,
            }
        )
    return checks


def int_value(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def summarize_cloudcanal_checks(run):
    checks = []
    for step in run.get("steps") or []:
        if not str(step.get("name") or "").endswith("-cloudcanal-check-result"):
            continue
        result = step.get("result") or {}
        children = result.get("children") or []
        loss = 0
        diff = 0
        task_count = 0
        child_ids = []
        incomplete = []
        failed_children = []
        for child in children:
            if child.get("jobId"):
                child_ids.append(child.get("jobId"))
            if not child.get("complete"):
                incomplete.append(child.get("jobId"))
            if not child.get("ok"):
                failed_children.append(child.get("jobId"))
            for task in child.get("tasks") or []:
                task_count += 1
                loss += int_value(task.get("loss"))
                diff += int_value(task.get("diff"))
        checks.append(
            {
                "name": step.get("name"),
                "ok": bool(result.get("ok")),
                "complete": bool(result.get("complete")),
                "childJobIds": child_ids,
                "childCount": len(children),
                "taskCount": task_count,
                "loss": loss,
                "diff": diff,
                "incompleteChildIds": incomplete[:6],
                "failedChildIds": failed_children[:6],
            }
        )
    return checks


def summarize_log_steps(run):
    logs = []
    for step in run.get("steps") or []:
        result = step.get("result")
        if step.get("phase") != "LOGS" or not isinstance(result, dict):
            continue
        summary = result.get("summary") or {}
        categories = summary.get("categories") or []
        if isinstance(categories, dict):
            categories = [str(key) + ":" + str(value) for key, value in sorted(categories.items())]
        logs.append(
            {
                "name": step.get("name"),
                "path": result.get("path"),
                "recordCount": result.get("recordCount", result.get("interestingRecordCount")),
                "categories": categories,
                "samples": (summary.get("samples") or [])[:3],
            }
        )
    return logs


def append_run_diagnostics(lines, run, indent=""):
    phases = summarize_run_phases(run)
    if phases:
        lines.append(indent + "phaseSummary:")
        for row in phases:
            lines.append(
                indent
                + "  - `"
                + str(row.get("phase"))
                + "` status=`"
                + str(row.get("status"))
                + "` steps=`"
                + str(row.get("steps"))
                + "`"
            )
    local_checks = summarize_local_checks(run)
    if local_checks:
        lines.append(indent + "localChecks:")
        for check in local_checks:
            lines.append(
                indent
                + "  - `"
                + str(check.get("name"))
                + "` ok=`"
                + str(check.get("ok"))
                + "` mode=`"
                + str(check.get("checkMode"))
                + "` tables=`"
                + str(check.get("tableCount"))
                + "` mismatches=`"
                + str(check.get("mismatchCount"))
                + "`"
            )
            for mismatch in check.get("mismatches") or []:
                target_table = mismatch.get("targetTable") or mismatch.get("table")
                lines.append(
                    indent
                    + "    mismatch `"
                    + str(mismatch.get("table"))
                    + "` -> `"
                    + str(target_table)
                    + "` rows=`"
                    + str(mismatch.get("sourceRows"))
                    + "/"
                    + str(mismatch.get("targetRows"))
                    + "` exists=`"
                    + str(mismatch.get("sourceExists"))
                    + "/"
                    + str(mismatch.get("targetExists"))
                    + "`"
                )
    cloudcanal_checks = summarize_cloudcanal_checks(run)
    if cloudcanal_checks:
        lines.append(indent + "cloudcanalChecks:")
        for check in cloudcanal_checks:
            lines.append(
                indent
                + "  - `"
                + str(check.get("name"))
                + "` ok=`"
                + str(check.get("ok"))
                + "` complete=`"
                + str(check.get("complete"))
                + "` children=`"
                + ",".join(str(value) for value in check.get("childJobIds") or [])
                + "` loss=`"
                + str(check.get("loss"))
                + "` diff=`"
                + str(check.get("diff"))
                + "`"
            )
    log_steps = summarize_log_steps(run)
    if log_steps:
        lines.append(indent + "stageLogs:")
        for log_step in log_steps:
            lines.append(
                indent
                + "  - `"
                + str(log_step.get("name"))
                + "` path=`"
                + str(log_step.get("path"))
                + "` records=`"
                + str(log_step.get("recordCount"))
                + "`"
            )
            if log_step.get("categories"):
                lines.append(indent + "    categories: `" + ",".join(str(value) for value in log_step.get("categories") or []) + "`")
            for sample in log_step.get("samples") or []:
                lines.append(indent + "    sample: `" + str(sample) + "`")


def render_batch_report(batch):
    pairs = batch.get("pairs") or batch.get("items") or []
    lines = [
        "# CloudCanal Batch Autotest Report",
        "",
        "- runId: `" + str(batch.get("runId")) + "`",
        "- mode: `" + str(batch.get("mode")) + "`",
        "- batchNo: `" + str(batch.get("batchNo")) + "`",
        "- pairCount: `" + str(len(pairs)) + "`",
        "- maxConcurrency: `" + str(batch.get("maxConcurrency")) + "`",
        "- result: `" + ("PASS" if batch.get("ok") else "FAIL") + "`",
        "- cleanup: `" + ("performed" if batch.get("cleanupAfterRun") else "not performed automatically") + "`",
        "",
        "## Pairs",
        "",
    ]
    for item in pairs:
        pair = item.get("pair") or item
        line = (
            "- `"
            + str(item.get("status"))
            + "` "
            + str(pair.get("sourceDataSourceId"))
            + "("
            + str(pair.get("sourceType"))
            + ") -> "
            + str(pair.get("targetDataSourceId"))
            + "("
            + str(pair.get("targetType"))
            + ")"
        )
        lines.append(line)
        run = None
        if item.get("runJson"):
            lines.append("  runJson: `" + str(item.get("runJson")) + "`")
            try:
                run = read_json_file(item.get("runJson"))
            except Exception as e:
                lines.append("  runJsonReadError: `" + str(e) + "`")
        if run:
            append_run_diagnostics(lines, run, indent="  ")
        if item.get("jobId"):
            lines.append("  jobId: `" + str(item.get("jobId")) + "`")
        if item.get("childJobIds"):
            lines.append("  childJobIds: `" + ",".join(str(value) for value in item.get("childJobIds")) + "`")
        if item.get("sourceSchema") or item.get("targetSchema"):
            lines.append("  schemas: `" + str(item.get("sourceSchema")) + "` -> `" + str(item.get("targetSchema")) + "`")
        if item.get("failurePhase"):
            lines.append("  failurePhase: `" + str(item.get("failurePhase")) + "`")
        if isinstance(item.get("failureLogs"), dict) and item["failureLogs"].get("path"):
            lines.append("  failureLogs: `" + str(item["failureLogs"].get("path")) + "`")
            summary = item["failureLogs"].get("summary") or {}
            if summary.get("categories"):
                lines.append("  logCategories: `" + ",".join(str(value) for value in summary.get("categories") or []) + "`")
            for sample in summary.get("samples") or []:
                lines.append("  logSample: `" + str(sample) + "`")
        run_logs = item.get("stageLogSummary") or []
        for log_item in run_logs:
            lines.append(
                "  stageLogs: `"
                + str(log_item.get("stage"))
                + "` path=`"
                + str(log_item.get("path"))
                + "` interesting="
                + str(log_item.get("interestingRecordCount"))
            )
            summary = log_item.get("summary") or {}
            if summary.get("categories"):
                lines.append("  stageLogCategories: `" + ",".join(str(value) for value in summary.get("categories") or []) + "`")
            for sample in (summary.get("samples") or [])[:3]:
                lines.append("  stageLogSample: `" + str(sample) + "`")
        if isinstance(item.get("isolation"), dict):
            isolation = item.get("isolation") or {}
            lines.append("  isolation: `" + json.dumps(isolation, ensure_ascii=False, sort_keys=True)[:1000] + "`")
        if item.get("error"):
            lines.append("  error: `" + str(item.get("error")) + "`")
        if item.get("followupCommands"):
            lines.append("  followup:")
            for command in item.get("followupCommands") or []:
                lines.append("    - `" + command + "`")
    return "\n".join(lines) + "\n"


def run_batch_pair(args, pair, index, run_id, credentials, output_dir, client):
    item = {"pairIndex": index, "pair": pair, "status": "PENDING"}
    pair_args = batch_pair_args(args, pair, index, run_id, credentials)
    pair_args.autotest_output_dir = output_dir
    pair_args.pair_index = index
    item["sourceSchema"] = pair_args.source_schema
    item["targetSchema"] = pair_args.target_schema
    if args.dry_run:
        item["status"] = "DRY_RUN"
        item["planned"] = {
            "jobName": pair_args.job_name,
            "profile": pair_args.profile,
            "mode": pair_args.mode,
            "rows": pair_args.rows,
            "crudRounds": pair_args.crud_rounds,
            "sqlCheck": pair_args.sql_check,
            "addCheckChild": pair_args.add_check_child,
        }
        item["followupCommands"] = followup_commands(item)
        return item
    if not pair.get("fullDataVerificationReady") and not args.include_unready:
        item["status"] = "SKIPPED"
        item["error"] = "pair is not full-data-verification ready"
        item["followupCommands"] = followup_commands(item)
        return item

    try:
        run = run_autotest_pair(pair_args, client)
    except Exception as e:
        item["status"] = "ERROR"
        item["error"] = str(e)
        fill_error_context(client, item, e, output_dir)
        maybe_isolate_item(args, client, item)
        item["followupCommands"] = followup_commands(item)
        return item
    item["status"] = "PASS" if run.get("ok") else (run.get("failurePhase") or "FAIL")
    if run.get("failurePhase"):
        item["failurePhase"] = run.get("failurePhase")
    if run.get("error"):
        item["error"] = run.get("error")
    item["jobId"] = run_job_id(run)
    item["childJobIds"] = run_child_job_ids(run)
    if item.get("jobId"):
        try:
            apply_job_context(item, query_job(client, item["jobId"]))
        except Exception:
            pass
    run_json = os.path.join(output_dir, "pair-" + str(index) + "-run.json")
    write_json_file(run_json, run)
    item["runJson"] = run_json
    item["phaseSummary"] = summarize_run_phases(run)
    item["localChecks"] = summarize_local_checks(run)
    item["cloudcanalChecks"] = summarize_cloudcanal_checks(run)
    if item["status"] != "PASS" and args.collect_failure_logs and item.get("jobId"):
        try:
            item["failureLogs"] = collect_task_logs(client, query_job(client, item["jobId"]), output_dir, index)
        except Exception as e:
            item["failureLogs"] = {"error": str(e)}
        maybe_isolate_item(args, client, item)
    stage_logs = []
    for step in run.get("steps") or []:
        if step.get("phase") == "LOGS" and isinstance(step.get("result"), dict):
            result = dict(step.get("result"))
            result["stage"] = step.get("name")
            stage_logs.append(result)
    if stage_logs:
        item["stageLogSummary"] = stage_logs
    if args.cleanup_after_run:
        item["cleanup"] = cleanup_batch_pair(client, pair_args)
    item["followupCommands"] = followup_commands(item)
    return item


def autotest_batch_run_cmd(args, client):
    run_id = args.run_id or timestamp_tag()
    output_dir = args.output_dir or os.path.join("/tmp", "cloudcanal-autotest-" + safe_identifier_part(run_id))
    os.makedirs(output_dir, exist_ok=True)
    credentials = read_json_arg(args.credential_json, {}) or {}
    if args.matrix_json:
        matrix = read_json_arg(args.matrix_json, {}) or {}
    else:
        matrix_args = SimpleNamespace(
            payload_json=args.payload_json,
            page_size=args.page_size,
            life_cycle_state=args.life_cycle_state,
            source_type=args.source_type,
            target_type=args.target_type,
            desc_prefix=args.desc_prefix,
            source_desc_prefix=args.source_desc_prefix,
            target_desc_prefix=args.target_desc_prefix,
            exclude_type=args.exclude_type,
            include_same=args.include_same,
            ready_only=not args.include_unready,
            batch_size=args.batch_size,
            batch_no=args.batch_no or 1,
            summary_only=False,
            output=None,
        )
        matrix = build_autotest_matrix(matrix_args, client)
    pairs, selected_batch_no = selected_pairs_from_matrix(matrix, args.batch_no, args.all_batches)
    pairs = filter_pairs_for_args(pairs, args)
    if not args.include_unready:
        pairs = [pair for pair in pairs if pair.get("fullDataVerificationReady")]
    if not args.batch_no and not args.all_batches and selected_batch_no:
        args.batch_no = selected_batch_no
    batch = {
        "runId": run_id,
        "mode": args.test_mode,
        "batchNo": selected_batch_no,
        "outputDir": output_dir,
        "cleanupAfterRun": bool(args.cleanup_after_run),
        "maxConcurrency": max(int(args.max_concurrency or 1), 1),
        "matrixSummary": {key: matrix.get(key) for key in ("datasourceCount", "sourceCount", "targetCount", "pairCount", "batchSize", "batchCount")},
        "pairs": [{"pairIndex": index, "pair": pair, "status": "PENDING"} for index, pair in enumerate(pairs, 1)],
        "ok": True,
    }
    batch_json = os.path.join(output_dir, "batch-result.json")
    write_json_file(batch_json, batch)
    max_workers = max(int(args.max_concurrency or 1), 1)
    if max_workers == 1:
        for index, pair in enumerate(pairs, 1):
            try:
                result_item = run_batch_pair(args, pair, index, run_id, credentials, output_dir, client)
            except Exception as e:
                result_item = {"pairIndex": index, "pair": pair, "status": "ERROR", "error": str(e)}
            batch["pairs"][index - 1] = result_item
            batch["ok"] = batch["ok"] and result_item.get("status") in ("PASS", "DRY_RUN", "SKIPPED")
            write_json_file(batch_json, batch)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_batch_pair, args, pair, index, run_id, credentials, output_dir, clone_client(client)): index
                for index, pair in enumerate(pairs, 1)
            }
            for future in as_completed(futures):
                index = futures[future]
                pair = pairs[index - 1]
                try:
                    result_item = future.result()
                except Exception as e:
                    result_item = {"pairIndex": index, "pair": pair, "status": "ERROR", "error": str(e)}
                batch["pairs"][index - 1] = result_item
                batch["ok"] = batch["ok"] and result_item.get("status") in ("PASS", "DRY_RUN", "SKIPPED")
                write_json_file(batch_json, batch)
    report_path = os.path.join(output_dir, "batch-report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(render_batch_report(batch))
    batch["batchJson"] = batch_json
    batch["report"] = report_path
    write_json_file(batch_json, batch)
    print_json({"ok": batch["ok"], "runId": run_id, "batchJson": batch_json, "report": report_path, "pairCount": len(batch["pairs"])})
    return 0 if batch["ok"] else 2


def autotest_report_cmd(args, _client):
    with open(args.run_json, "r", encoding="utf-8") as f:
        run = json.load(f)
    lines = [
        "# CloudCanal Autotest Report",
        "",
        "- mode: `" + str(run.get("mode")) + "`",
        "- source: `" + str(run.get("sourceDataSourceId")) + "` (" + str(run.get("sourceType")) + ")",
        "- target: `" + str(run.get("targetDataSourceId")) + "` (" + str(run.get("targetType")) + ")",
        "- schemas: `" + str(run.get("sourceSchema")) + "` -> `" + str(run.get("targetSchema")) + "`",
        "- profile: `" + str(run.get("profile")) + "`",
        "- result: `" + ("PASS" if run.get("ok") else "FAIL") + "`",
        "- failurePhase: `" + str(run.get("failurePhase") or "") + "`",
        "- cleanup: `not performed automatically`",
        "",
        "## Summary",
        "",
    ]
    append_run_diagnostics(lines, run)
    lines.extend(
        [
            "",
            "## Steps",
            "",
        ]
    )
    for step in run.get("steps") or []:
        lines.append("- `" + str(step.get("name")) + "`")
        if "phase" in step:
            lines.append("  phase: `" + str(step.get("phase")) + "`")
        if "ok" in step:
            lines.append("  ok: `" + str(step.get("ok")) + "`")
        if step.get("error"):
            lines.append("  error: `" + str(step.get("error")) + "`")
        result = step.get("result")
        if isinstance(result, dict):
            if "jobId" in result:
                lines.append("  jobId: `" + str(result.get("jobId")) + "`")
            if "ok" in result:
                lines.append("  ok: `" + str(result.get("ok")) + "`")
            if "sourceColumnCounts" in result:
                lines.append("  sourceColumnCounts: `" + json.dumps(result.get("sourceColumnCounts"), ensure_ascii=False, sort_keys=True) + "`")
            if isinstance(result.get("startResult"), dict):
                lines.append("  startAction: `" + str(result["startResult"].get("action")) + "`")
            if "tables" in result and isinstance(result.get("tables"), list):
                table_results = [t for t in result["tables"] if isinstance(t, dict)]
                if table_results:
                    bad = [t for t in table_results if not t.get("ok", True)]
                    lines.append("  tables: `" + str(len(table_results)) + "`, mismatched: `" + str(len(bad)) + "`")
                else:
                    lines.append("  tables: `" + str(len(result["tables"])) + "`")
    text = "\n".join(lines) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(args.output)
    else:
        print(text)
    return 0
