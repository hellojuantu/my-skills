import argparse
import sys

from cc_console.auth import client_from_args, login_cmd
from cc_console.checkjob import replay_check_job_cmd, wait_check_job_cmd
from cc_console.client import ApiError
from cc_console.clusters import list_cluster_cmd
from cc_console.consolejob import list_console_jobs_cmd, operate_console_task_cmd, query_console_job_cmd
from cc_console.datajob import (
    add_check_child_job_cmd,
    add_revise_task_cmd,
    active_fsm_datajob_cmd,
    attach_incre_task_cmd,
    can_add_revise_task_cmd,
    activate_fsm_cmd,
    create_datajob_cmd,
    delete_datajob_cmd,
    detach_incre_task_cmd,
    edit_job_cmd,
    export_job_config_cmd,
    fetch_current_pos_cmd,
    generate_migration_tip_cmd,
    get_followed_jobs_cmd,
    inactivate_fsm_cmd,
    get_job_config_cmd,
    job_config_template_cmd,
    job_extra_configs_cmd,
    list_fsm_cmd,
    list_datajobs_cmd,
    list_check_tasks_cmd,
    list_job_config_tags_cmd,
    list_job_configs_cmd,
    list_columns_cmd,
    list_dbs_cmd,
    list_simple_datajobs_cmd,
    list_specs_cmd,
    list_table_uniqs_cmd,
    list_tables_cmd,
    manual_merge_edit_job_cmd,
    manual_schedule_cmd,
    operate_datajobs_cmd,
    position_ops_cmd,
    precheck_cmd,
    query_fsm_cmd,
    query_datajob_cmd,
    query_datajob_schema_cmd,
    query_job_options_cmd,
    replay_datajob_cmd,
    reset_pos_to_current_cmd,
    reset_position_cmd,
    restart_datajob_cmd,
    start_datajob_cmd,
    stop_datajob_cmd,
    time_schedule_cmd,
    type_mapping_cmd,
    update_incre_pos_cmd,
    update_job_configs_cmd,
    update_job_desc_cmd,
    update_job_level_cmd,
    update_job_options_cmd,
    update_transfer_object_cmd,
)
from cc_console.datasource import create_datasource_cmd, delete_datasource_cmd, query_kv_defs_cmd, test_datasource_cmd
from cc_console.datasource import (
    delete_datasource_account_cmd,
    list_datasources_cmd,
    query_datasource_cmd,
    query_datasource_config_cmd,
    query_datasource_kv_config_cmd,
    query_llm_config_cmd,
    update_datasource_account_cmd,
    update_datasource_aksk_cmd,
    update_datasource_desc_cmd,
    update_datasource_host_cmd,
    upsert_datasource_config_cmd,
)
from cc_console.doctor import doctor_cmd
from cc_console.logview import grep_operation_log_cmd, tail_task_log_cmd, tail_worker_log_cmd
from cc_console.raw import call_api_cmd, call_service_cmd, list_services_cmd


def build_parser():
    parser = argparse.ArgumentParser(description="CloudCanal/RDP console automation.")
    subparsers = parser.add_subparsers(dest="command")

    def add_common(p, include_type=False, include_deploy_type=False):
        p.add_argument("--base-url", help="Console origin, e.g. https://example.com. Or use CC_BASE_URL.")
        p.add_argument("--cookie", help="Raw Cookie header. Prefer CC_COOKIE env or --cookie-file.")
        p.add_argument("--cookie-file", help="File containing raw Cookie header.")
        p.add_argument("--csrf-token", help="Optional csrf-token header.")
        p.add_argument("--header", action="append", default=[], metavar="NAME=VALUE", help="Extra request header. May repeat.")
        p.add_argument("--timeout", type=int, default=30)
        if include_deploy_type:
            p.add_argument("--deploy-type", default="SELF_MAINTENANCE")
        if include_type:
            p.add_argument("--type", required=True, help="Datasource type, e.g. mysql/tidb/oracle/starrocks/postgres/kafka/redis.")

    login = subparsers.add_parser("login", help="Login and print/save console cookie.")
    login.add_argument("--base-url", help="Console origin, e.g. https://example.com. Or use CC_BASE_URL.")
    login.add_argument("--csrf-token", help="Optional csrf-token header.")
    login.add_argument("--timeout", type=int, default=30)
    login.add_argument("--account", help="Console account. Falls back to CC_ACCOUNT or prompts for input.")
    login.add_argument("--password", help="Console password. Falls back to CC_PASSWORD or prompts for input.")
    login.add_argument("--account-type", default="PRIMARY_ACCOUNT", choices=("PRIMARY_ACCOUNT", "SUB_ACCOUNT"))
    login.add_argument("--login-type", default="PASSWORD")
    login.add_argument("--password-encrypted", action="store_true", help="Treat --password as already SM2 encrypted.")
    login.add_argument("--save-cookie", help="Write jwt_token cookie to this file.")
    login.add_argument("--print-cookie", action="store_true", help="Print cookie even when --save-cookie is used.")
    login.set_defaults(func=lambda args: login_cmd(args))

    doctor = subparsers.add_parser("doctor", help="Check local setup for sharing/running this skill.")
    doctor.add_argument("--base-url", help="Console origin, e.g. https://example.com. Or use CC_BASE_URL.")
    doctor.add_argument("--cookie", help="Raw Cookie header. Prefer CC_COOKIE env or --cookie-file.")
    doctor.add_argument("--cookie-file", help="File containing raw Cookie header.")
    doctor.add_argument("--csrf-token", help="Optional csrf-token header.")
    doctor.add_argument("--timeout", type=int, default=30)
    doctor.add_argument("--frontend-dir", help="Path to clouddm-web checkout. Or use CLOUDCANAL_WEB_DIR.")
    doctor.add_argument("--check-api", action="store_true", help="Call the console API and query the default cluster.")
    doctor.set_defaults(func=lambda args: doctor_cmd(args))

    list_services = subparsers.add_parser("list-services", help="List frontend API service keys from clouddm-web.")
    list_services.add_argument("--frontend-dir", help="Path to clouddm-web checkout. Or use CLOUDCANAL_WEB_DIR.")
    list_services.add_argument("--api-file", action="append", help="Limit to one frontend api file, e.g. dataJob.js. May repeat.")
    list_services.add_argument("--core", action="store_true", help="Limit to the core datasource/job operation API files.")
    list_services.add_argument("--filter", help="Filter by service name or endpoint substring.")
    list_services.add_argument("--format", choices=("json", "markdown"), default="markdown")
    list_services.set_defaults(func=lambda args: list_services_cmd(args))

    call_api = subparsers.add_parser("call-api", help="Call a frontend console API path directly for parity testing.")
    add_common(call_api)
    call_api.add_argument("--path", required=True, help="Frontend API path, e.g. /cloudcanal/console/api/v1/inner/datajob/queryjob.")
    call_api.add_argument("--method", type=str.upper, choices=("POST", "GET"), default="POST")
    call_api.add_argument("--payload-json", help="JSON payload or @file. Defaults to {}.")
    call_api.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="JSON payload field override. May repeat.")
    call_api.add_argument("--multipart", action="store_true", help="POST multipart/form-data instead of JSON.")
    call_api.add_argument("--payload-part-name", default="data", help="Multipart field name for --payload-json/--set payload.")
    call_api.add_argument("--part", action="append", default=[], metavar="NAME=VALUE", help="Multipart text field. @file reads text.")
    call_api.add_argument("--json-part", action="append", default=[], metavar="NAME=JSON", help="Multipart JSON part. JSON may be @file.")
    call_api.add_argument("--file-part", action="append", default=[], metavar="NAME=PATH", help="Multipart file field.")
    call_api.add_argument("--response", choices=("json", "text", "raw"), default="json", help="How to handle the response body.")
    call_api.add_argument("--output", help="Write text/raw response body to this file.")
    call_api.add_argument("--dry-run", action="store_true")
    call_api.set_defaults(func=lambda args: call_api_cmd(args, None if args.dry_run else client_from_args(args)))

    call_service = subparsers.add_parser("call-service", help="Resolve a frontend API service name from clouddm-web and call it.")
    add_common(call_service)
    call_service.add_argument("--service", required=True, help="Frontend service key, e.g. ccDataJobQueryJob.")
    call_service.add_argument("--frontend-dir", help="Path to clouddm-web checkout. Or use CLOUDCANAL_WEB_DIR.")
    call_service.add_argument("--api-file", action="append", help="Limit lookup to one frontend api file, e.g. dataJob.js. May repeat.")
    call_service.add_argument("--method", type=str.upper, choices=("POST", "GET"), default="POST")
    call_service.add_argument("--payload-json", help="JSON payload or @file. Defaults to {}.")
    call_service.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="JSON payload field override. May repeat.")
    call_service.add_argument("--multipart", action="store_true", help="POST multipart/form-data instead of JSON.")
    call_service.add_argument("--payload-part-name", default="data", help="Multipart field name for --payload-json/--set payload.")
    call_service.add_argument("--part", action="append", default=[], metavar="NAME=VALUE", help="Multipart text field. @file reads text.")
    call_service.add_argument("--json-part", action="append", default=[], metavar="NAME=JSON", help="Multipart JSON part. JSON may be @file.")
    call_service.add_argument("--file-part", action="append", default=[], metavar="NAME=PATH", help="Multipart file field.")
    call_service.add_argument("--response", choices=("json", "text", "raw"), default="json", help="How to handle the response body.")
    call_service.add_argument("--output", help="Write text/raw response body to this file.")
    call_service.add_argument("--dry-run", action="store_true")
    call_service.set_defaults(func=lambda args: call_service_cmd(args, None if args.dry_run else client_from_args(args)))

    query = subparsers.add_parser("query-kv", help="Query dynamic extra datasource configs.")
    add_common(query, include_type=True, include_deploy_type=True)
    query.set_defaults(func=lambda args: query_kv_defs_cmd(args, client_from_args(args)))

    list_ds = subparsers.add_parser("list-ds", aliases=["datasources"], help="List datasources by frontend listbycondition API.")
    add_common(list_ds)
    list_ds.add_argument("--type", help="Filter by datasource type alias.")
    list_ds.add_argument("--data-source-type", help="Filter by frontend dataSourceType field.")
    list_ds.add_argument("--deploy-type")
    list_ds.add_argument("--desc", help="Filter by instanceDesc.")
    list_ds.add_argument("--life-cycle-state")
    list_ds.add_argument("--use-visibility", action="store_true")
    list_ds.add_argument("--load-appro-info", action="store_true")
    list_ds.add_argument("--payload-json", help="Raw listbycondition payload JSON or @file; merged last.")
    list_ds.set_defaults(func=lambda args: list_datasources_cmd(args, client_from_args(args)))

    query_ds = subparsers.add_parser("query-ds", aliases=["datasource"], help="Query datasource detail.")
    add_common(query_ds)
    query_ds.add_argument("--data-source-id", required=True)
    query_ds.set_defaults(func=lambda args: query_datasource_cmd(args, client_from_args(args)))

    query_ds_config = subparsers.add_parser("query-ds-config", aliases=["ds-config"], help="Query datasource runtime configs.")
    add_common(query_ds_config)
    query_ds_config.add_argument("--data-source-id", required=True)
    query_ds_config.add_argument("--payload-json", help="Raw querydsconfig payload JSON or @file; merged last.")
    query_ds_config.set_defaults(func=lambda args: query_datasource_config_cmd(args, client_from_args(args)))

    query_ds_kv_config = subparsers.add_parser("query-ds-kv-config", aliases=["ds-kv-config"], help="Query datasource kv config values.")
    add_common(query_ds_kv_config)
    query_ds_kv_config.add_argument("--data-source-id", required=True)
    query_ds_kv_config.add_argument("--payload-json", help="Raw dsKvConfig payload JSON or @file; merged last.")
    query_ds_kv_config.set_defaults(func=lambda args: query_datasource_kv_config_cmd(args, client_from_args(args)))

    query_llm = subparsers.add_parser("query-llm-config", aliases=["llm-config"], help="Query LLM datasource config.")
    add_common(query_llm)
    query_llm.add_argument("--data-source-id", required=True)
    query_llm.add_argument("--data-source-type")
    query_llm.add_argument("--payload-json", help="Raw queryllmconfig payload JSON or @file; merged last.")
    query_llm.set_defaults(func=lambda args: query_llm_config_cmd(args, client_from_args(args)))

    create = subparsers.add_parser("create", help="Create datasource.")
    add_common(create, include_type=True, include_deploy_type=True)
    create.add_argument("--host", help="Datasource host. Without port, default port is appended.")
    create.add_argument("--port", type=int, help="Datasource port.")
    create.add_argument("--host-type", choices=("private", "public"), default="private")
    create.add_argument("--private-host", help="Override privateHost sent to backend.")
    create.add_argument("--public-host", help="Override publicHost sent to backend.")
    create.add_argument("--db", help="Default database. For Oracle, SID/service/PDB name.")
    create.add_argument("--user", help="Datasource account.")
    create.add_argument("--password", help="Datasource password. If omitted, prompt hides input.")
    create.add_argument("--as-sysdba", action="store_true", help="Oracle only: append 'as SYSDBA' to account.")
    create.add_argument("--desc", help="Datasource instanceDesc.")
    create.add_argument("--region", default="customer")
    create.add_argument("--security-type", default="USER_PASSWD")
    create.add_argument("--info-fetch-type", default="MANUALLY_FILL")
    create.add_argument("--connect-type", help="Oracle: ORACLE_SID/ORACLE_SERVICE/ORACLE_TNS/ORACLE_PDB.")
    create.add_argument("--access-key")
    create.add_argument("--secret-key")
    create.add_argument("--security-file", help="TLS truststore/CA file path, sent as securityFile.")
    create.add_argument("--client-security-file", help="TLS keystore file path, sent as clientSecurityFile.")
    create.add_argument("--secret-file", help="Client secret/cert file path, sent as secretFile.")
    create.add_argument("--security-file-password")
    create.add_argument("--client-security-file-password")
    create.add_argument("--secret-file-password")
    create.add_argument("--client-trust-store-password")
    create.add_argument("--instance-id")
    create.add_argument("--version")
    create.add_argument("--driver")
    create.add_argument("--bind-cluster-id", type=int)
    create.add_argument("--env-id", type=int)
    create.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="Extra kv override.")
    create.add_argument("--non-interactive", action="store_true", help="Use args/defaults only; do not prompt.")
    create.add_argument("--strict-required", action="store_true", help="Fail when a required extra kv has no value.")
    create.add_argument("--dry-run", action="store_true", help="Print masked payload and do not create.")
    create.add_argument("--test-after-add", action="store_true", help="Test saved datasource after add.")
    create.add_argument("--cluster-id", type=int, help="Cluster id used by --test-after-add. Or use CC_CLUSTER_ID.")
    create.add_argument("--cluster-name-like", help="Find cluster by name when --cluster-id is omitted.")
    create.add_argument("--test-host", help="Override host used by --test-after-add.")
    create.add_argument("--test-host-type", choices=("private", "public", "PRIVATE", "PUBLIC"), help="Host type used by --test-after-add.")
    create.set_defaults(func=lambda args: create_datasource_cmd(args, client_from_args(args)))

    test = subparsers.add_parser("test", help="Test an existing datasource connection.")
    add_common(test)
    test.add_argument("--data-source-id", required=True)
    test.add_argument("--cluster-id", type=int, help="Cluster id used to test connection. Or use CC_CLUSTER_ID.")
    test.add_argument("--cluster-name-like", help="Find cluster by name when --cluster-id is omitted.")
    test.add_argument("--host", help="Override host used to test connection.")
    test.add_argument("--host-type", choices=("private", "public", "PRIVATE", "PUBLIC"))
    test.add_argument("--non-interactive", action="store_true", help="Use args/env only; do not prompt.")
    test.set_defaults(func=lambda args: test_datasource_cmd(args, client_from_args(args)))

    ds_update_desc = subparsers.add_parser("update-ds-desc", aliases=["ds-update-desc"], help="Update datasource description.")
    add_common(ds_update_desc)
    ds_update_desc.add_argument("--data-source-id", required=True)
    ds_update_desc.add_argument("--desc", required=True)
    ds_update_desc.add_argument("--dry-run", action="store_true")
    ds_update_desc.set_defaults(func=lambda args: update_datasource_desc_cmd(args, client_from_args(args)))

    ds_update_host = subparsers.add_parser("update-ds-host", aliases=["ds-update-host"], help="Update datasource private/public host.")
    add_common(ds_update_host)
    ds_update_host.add_argument("--data-source-id", required=True)
    ds_update_host.add_argument("--host", required=True)
    ds_update_host.add_argument("--host-type", required=True, choices=("private", "public", "PRIVATE", "PUBLIC"))
    ds_update_host.add_argument("--dry-run", action="store_true")
    ds_update_host.set_defaults(func=lambda args: update_datasource_host_cmd(args, client_from_args(args)))

    ds_update_account = subparsers.add_parser("update-ds-account", aliases=["ds-update-account"], help="Update datasource account/password security data.")
    add_common(ds_update_account)
    ds_update_account.add_argument("--data-source-id", required=True)
    ds_update_account.add_argument("--user", required=True)
    ds_update_account.add_argument("--password")
    ds_update_account.add_argument("--security-type", default="USER_PASSWD")
    ds_update_account.add_argument("--access-key")
    ds_update_account.add_argument("--secret-key")
    ds_update_account.add_argument("--security-file", help="TLS truststore/CA file path, sent as securityFile.")
    ds_update_account.add_argument("--client-security-file", help="TLS keystore file path, sent as clientSecurityFile.")
    ds_update_account.add_argument("--secret-file", help="Client secret/cert file path, sent as secretFile.")
    ds_update_account.add_argument("--security-file-password")
    ds_update_account.add_argument("--secret-file-password")
    ds_update_account.add_argument("--client-security-file-password")
    ds_update_account.add_argument("--client-trust-store-password")
    ds_update_account.add_argument("--payload-json", help="Raw UpdateSecurityInfoFO JSON or @file; merged last.")
    ds_update_account.add_argument("--dry-run", action="store_true")
    ds_update_account.set_defaults(func=lambda args: update_datasource_account_cmd(args, client_from_args(args)))

    ds_update_aksk = subparsers.add_parser("update-ds-aksk", aliases=["ds-update-aksk"], help="Update datasource Aliyun accessKey/secretKey.")
    add_common(ds_update_aksk)
    ds_update_aksk.add_argument("--data-source-id", required=True)
    ds_update_aksk.add_argument("--access-key", required=True)
    ds_update_aksk.add_argument("--secret-key", required=True)
    ds_update_aksk.add_argument("--dry-run", action="store_true")
    ds_update_aksk.set_defaults(func=lambda args: update_datasource_aksk_cmd(args, client_from_args(args)))

    ds_delete_account = subparsers.add_parser("delete-ds-account", aliases=["ds-delete-account"], help="Delete datasource account/password.")
    add_common(ds_delete_account)
    ds_delete_account.add_argument("--data-source-id", required=True)
    ds_delete_account.add_argument("--dry-run", action="store_true")
    ds_delete_account.set_defaults(func=lambda args: delete_datasource_account_cmd(args, client_from_args(args)))

    ds_upsert_config = subparsers.add_parser("upsert-ds-config", aliases=["ds-upsert-config"], help="Upsert datasource dynamic kv configs.")
    add_common(ds_upsert_config)
    ds_upsert_config.add_argument("--data-source-id", required=True)
    ds_upsert_config.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="Update existing config. May repeat.")
    ds_upsert_config.add_argument("--create", action="append", default=[], metavar="KEY=VALUE", help="Create config if needed. May repeat.")
    ds_upsert_config.add_argument("--payload-json", help="Raw UpsertDsKvConfigFO JSON or @file; merged last.")
    ds_upsert_config.add_argument("--dry-run", action="store_true")
    ds_upsert_config.set_defaults(func=lambda args: upsert_datasource_config_cmd(args, client_from_args(args)))

    delete = subparsers.add_parser("delete", aliases=["cleanup"], help="Delete a datasource.")
    add_common(delete)
    delete.add_argument("--data-source-id", required=True)
    delete.add_argument("--yes", action="store_true", help="Skip delete confirmation.")
    delete.set_defaults(func=lambda args: delete_datasource_cmd(args, client_from_args(args)))

    clusters = subparsers.add_parser("clusters", help="List clusters or query default cluster.")
    add_common(clusters)
    clusters.add_argument("--default", action="store_true", help="Query default cluster only.")
    clusters.add_argument("--cluster-name-like", help="Filter cluster name.")
    clusters.set_defaults(func=lambda args: list_cluster_cmd(args, client_from_args(args)))

    wait_check_job = subparsers.add_parser("wait-check-job", aliases=["check-job-wait"], help="Wait for one or more CloudCanal check jobs and summarize loss/diff.")
    add_common(wait_check_job)
    wait_check_job.add_argument("--job-id", action="append", required=True, help="Check job id. May repeat.")
    wait_check_job.add_argument("--timeout-seconds", type=int, default=180)
    wait_check_job.set_defaults(func=lambda args: wait_check_job_cmd(args, client_from_args(args)))

    replay_check_job = subparsers.add_parser("replay-check-job", aliases=["check-job-replay"], help="Replay one or more CloudCanal check jobs and wait for loss/diff result.")
    add_common(replay_check_job)
    replay_check_job.add_argument("--job-id", action="append", required=True, help="Check job id. May repeat.")
    replay_check_job.add_argument("--timeout-seconds", type=int, default=180)
    replay_check_job.add_argument("--wait-before-seconds", type=int, default=5)
    replay_check_job.set_defaults(func=lambda args: replay_check_job_cmd(args, client_from_args(args)))

    def add_job_common(p):
        add_common(p)
        p.add_argument("--cluster-id", type=int, help="Cluster id. Or use CC_CLUSTER_ID.")
        p.add_argument("--cluster-name-like", help="Find cluster by name when --cluster-id is omitted.")
        p.add_argument("--non-interactive", action="store_true", help="Use args/env only; do not prompt.")

    create_job = subparsers.add_parser("create-job", aliases=["job-create"], help="Create data job.")
    add_job_common(create_job)
    create_job.add_argument("--source-ds-id", required=True)
    create_job.add_argument("--target-ds-id", required=True)
    create_job.add_argument("--source-type", help="Override source datasource type.")
    create_job.add_argument("--target-type", help="Override target datasource type.")
    create_job.add_argument("--source-host-type", choices=("private", "public", "PRIVATE", "PUBLIC"))
    create_job.add_argument("--target-host-type", choices=("private", "public", "PRIVATE", "PUBLIC"))
    create_job.add_argument("--mode", default="full-sync", choices=("full", "migration", "full-sync", "sync", "increment", "incremental", "check", "struct"))
    create_job.add_argument("--job-type", choices=("MIGRATION", "SYNC", "CHECK", "STRUCT_MIGRATION"))
    create_job.add_argument("--job-name", help="Specified task name.")
    create_job.add_argument("--desc", help="Task description.")
    create_job.add_argument("--level", default="P2")
    create_job.add_argument("--spec-id", type=int)
    create_job.add_argument("--source-db")
    create_job.add_argument("--source-schema")
    create_job.add_argument("--target-db")
    create_job.add_argument("--target-schema")
    create_job.add_argument("--target-table")
    create_job.add_argument("--table", action="append", default=[], help="Source table, or source=target. May repeat.")
    create_job.add_argument("--table-map", action="append", default=[], help="Explicit source=target table mapping. May repeat.")
    create_job.add_argument("--column-map", action="append", default=[], help="SRC=DST or TABLE:SRC=DST. May repeat.")
    create_job.add_argument("--source-schema-json", help="Raw sourceSchema JSON or @file.")
    create_job.add_argument("--target-schema-json", help="Raw targetSchema JSON or @file.")
    create_job.add_argument("--mapping-json", help="Raw mappingDef JSON or @file.")
    create_job.add_argument("--extra-json", help="Extra DataJobData fields JSON or @file.")
    create_job.add_argument("--processor-config-json", help="processorConfigList JSON or @file.")
    create_job.add_argument("--source-charset")
    create_job.add_argument("--target-charset")
    create_job.add_argument("--table-rule", help="Override common table mapping rule.")
    create_job.add_argument("--column-rule", help="Override common column mapping rule.")
    create_job.add_argument("--table-mapping-method", help="Override table mapping method, e.g. TABLE_TABLE/TABLE_TOPIC.")
    create_job.add_argument("--table-select-mode", default="LIST_ALL_AND_SELECT")
    create_job.add_argument("--auto-create-target", action="store_true")
    create_job.add_argument("--struct-migration", dest="struct_migration", action="store_true", default=None)
    create_job.add_argument("--no-struct-migration", dest="struct_migration", action="store_false")
    create_job.add_argument("--auto-start", action="store_true", help="Set autoStart in created task.")
    create_job.add_argument("--start-after-create", action="store_true", help="Wait for creation to finish, then start the job.")
    create_job.add_argument("--start-timeout-seconds", type=int, default=180, help="Time to wait for asynchronous creation.")
    create_job.add_argument("--short-term-num", type=int)
    create_job.add_argument("--key-conflict-strategy", default="IGNORE")
    create_job.add_argument("--filter-ddl", action="store_true")
    create_job.add_argument("--clean-target-before-full", action="store_true")
    create_job.add_argument("--skip-precheck", action="store_true")
    create_job.add_argument("--precheck-stage", default="final", choices=("final", "step-two", "step-three", "obj-necessary"))
    create_job.add_argument("--precheck-only", action="store_true", help="Run selected precheck stage and do not create.")
    create_job.add_argument("--ignore-precheck-fail", action="store_true")
    create_job.add_argument("--dry-run", action="store_true")
    create_job.set_defaults(func=lambda args: create_datajob_cmd(args, client_from_args(args)))

    query_job = subparsers.add_parser("query-job", aliases=["job-query"], help="Query data job.")
    add_common(query_job)
    query_job.add_argument("--job-id", required=True)
    query_job.set_defaults(func=lambda args: query_datajob_cmd(args, client_from_args(args)))

    list_jobs = subparsers.add_parser("list-jobs", aliases=["jobs"], help="List data jobs by page.")
    add_common(list_jobs)
    list_jobs.add_argument("--page-num", type=int, default=1)
    list_jobs.add_argument("--page-size", type=int, default=20)
    list_jobs.add_argument("--job-id", type=int)
    list_jobs.add_argument("--job-name")
    list_jobs.add_argument("--job-type")
    list_jobs.add_argument("--desc")
    list_jobs.add_argument("--source-ds-id", type=int)
    list_jobs.add_argument("--target-ds-id", type=int)
    list_jobs.add_argument("--worker-id", type=int)
    list_jobs.add_argument("--worker-ip")
    list_jobs.add_argument("--task-status")
    list_jobs.add_argument("--order-type")
    list_jobs.add_argument("--order-asc", action="store_true")
    list_jobs.add_argument("--transfer-obj-name")
    list_jobs.add_argument("--payload-json", help="Raw ListJobsByPageFO JSON or @file; merged last.")
    list_jobs.set_defaults(func=lambda args: list_datajobs_cmd(args, client_from_args(args)))

    list_simple_jobs = subparsers.add_parser("list-simple-jobs", aliases=["jobs-simple"], help="List simple jobs for selectors/search.")
    add_common(list_simple_jobs)
    list_simple_jobs.set_defaults(func=lambda args: list_simple_datajobs_cmd(args, client_from_args(args)))

    list_check_tasks = subparsers.add_parser("list-check-tasks", aliases=["check-tasks"], help="List check tasks.")
    add_common(list_check_tasks)
    list_check_tasks.set_defaults(func=lambda args: list_check_tasks_cmd(args, client_from_args(args)))

    followed_jobs = subparsers.add_parser("followed-jobs", aliases=["jobs-followed"], help="Get followed jobs.")
    add_common(followed_jobs)
    followed_jobs.add_argument("--page-num", type=int, default=1)
    followed_jobs.add_argument("--page-size", type=int, default=20)
    followed_jobs.add_argument("--payload-json", help="Raw getFollowedJob payload JSON or @file; merged last.")
    followed_jobs.set_defaults(func=lambda args: get_followed_jobs_cmd(args, client_from_args(args)))

    query_job_schema = subparsers.add_parser("query-job-schema", aliases=["job-schema"], help="Query current job schema/mapping detail.")
    add_common(query_job_schema)
    query_job_schema.add_argument("--job-id", required=True)
    query_job_schema.add_argument("--source-type", help="Override source datasource type.")
    query_job_schema.add_argument("--target-type", help="Override target datasource type.")
    query_job_schema.set_defaults(func=lambda args: query_datajob_schema_cmd(args, client_from_args(args)))

    tail_task_log = subparsers.add_parser("tail-task-log", aliases=["job-log", "task-log"], help="Tail CloudCanal task logs like the job detail log modal.")
    add_common(tail_task_log)
    tail_task_log.add_argument("--job-id", required=True)
    tail_task_log.add_argument("--task-id", help="Task id. If omitted, resolve from --task-type or current job state.")
    tail_task_log.add_argument("--task-type", help="BUILD_STRUCT/FULL/INCREMENT/CHECK/REVISE. Used when --task-id is omitted.")
    tail_task_log.add_argument("--end-row", type=int, default=0, help="Current endRow from prior response; 0 tails latest page.")
    tail_task_log.add_argument("--step", type=int, default=0, help="Use 200 or -200 to page like the frontend.")
    tail_task_log.add_argument("--file-name", help="Only print one log file from the response.")
    tail_task_log.add_argument("--contains", help="Only print log lines containing this string.")
    tail_task_log.add_argument("--text", action="store_true", help="Print log content as text instead of JSON.")
    tail_task_log.add_argument("--payload-json", help="Raw tail task log payload JSON or @file; merged last.")
    tail_task_log.add_argument("--dry-run", action="store_true")
    tail_task_log.set_defaults(func=lambda args: tail_task_log_cmd(args, client_from_args(args)))

    tail_worker_log = subparsers.add_parser("tail-worker-log", aliases=["worker-log"], help="Tail CloudCanal worker logs like the worker log modal.")
    add_common(tail_worker_log)
    tail_worker_log.add_argument("--worker-id", required=True)
    tail_worker_log.add_argument("--end-row", type=int, default=0)
    tail_worker_log.add_argument("--step", type=int, default=0)
    tail_worker_log.add_argument("--log-type", action="append", help="Fetched log type, e.g. WORKER_MAIN_LOG. May repeat.")
    tail_worker_log.add_argument("--file-name", help="Only print one log file from the response.")
    tail_worker_log.add_argument("--contains", help="Only print log lines containing this string.")
    tail_worker_log.add_argument("--text", action="store_true", help="Print log content as text instead of JSON.")
    tail_worker_log.add_argument("--payload-json", help="Raw tail worker log payload JSON or @file; merged last.")
    tail_worker_log.add_argument("--dry-run", action="store_true")
    tail_worker_log.set_defaults(func=lambda args: tail_worker_log_cmd(args, client_from_args(args)))

    grep_operation_log = subparsers.add_parser("grep-operation-log", aliases=["operation-log"], help="Query operation log detail by operation id.")
    add_common(grep_operation_log)
    grep_operation_log.add_argument("--operation-id")
    grep_operation_log.add_argument("--payload-json", help="Raw grep operation log payload JSON or @file; merged last.")
    grep_operation_log.add_argument("--dry-run", action="store_true")
    grep_operation_log.set_defaults(func=lambda args: grep_operation_log_cmd(args, client_from_args(args)))

    list_console_jobs = subparsers.add_parser("list-console-jobs", aliases=["console-jobs"], help="List CloudCanal async console jobs.")
    add_common(list_console_jobs)
    list_console_jobs.add_argument("--state", help="Console task state, e.g. FAILED/SUCCESS/EXECUTE.")
    list_console_jobs.add_argument("--label", help="Console job label, e.g. DATA_JOB_CREATE.")
    list_console_jobs.add_argument("--start-id", type=int, default=0)
    list_console_jobs.add_argument("--page-size", type=int, default=20)
    list_console_jobs.set_defaults(func=lambda args: list_console_jobs_cmd(args, client_from_args(args)))

    query_console_job = subparsers.add_parser("query-console-job", aliases=["console-job"], help="Query async console job detail by consoleJobId.")
    add_common(query_console_job)
    query_console_job.add_argument("--console-job-id", required=True)
    query_console_job.add_argument("--summary", action="store_true", help="Print failed task summary instead of full payload.")
    query_console_job.set_defaults(func=lambda args: query_console_job_cmd(args, client_from_args(args)))

    operate_console = subparsers.add_parser("operate-console-job", aliases=["console-job-op"], help="Retry/skip/cancel async console jobs like the frontend.")
    add_common(operate_console)
    operate_console.add_argument("--action", required=True, choices=("retry", "skip", "cancel"))
    operate_console.add_argument("--console-job-id", required=True)
    operate_console.add_argument("--console-task-id", help="Required for retry/skip task; empty for cancel job.")
    operate_console.add_argument("--dry-run", action="store_true")
    operate_console.set_defaults(func=lambda args: operate_console_task_cmd(args, client_from_args(args)))

    delete_job = subparsers.add_parser("delete-job", aliases=["job-delete"], help="Delete data job.")
    add_common(delete_job)
    delete_job.add_argument("--job-id", required=True)
    delete_job.add_argument("--job-name", help="Avoid an extra query when known.")
    delete_job.add_argument("--delete-children", action="store_true", help="Delete child jobs before deleting this job.")
    delete_job.add_argument("--stop-first", action="store_true", help="Try stop-job before delete; ignores not-running stop errors.")
    delete_job.add_argument("--inactivate-fsm", action="store_true", help="Resolve and inactivate the job FSM before delete.")
    delete_job.add_argument("--dry-run", action="store_true")
    delete_job.set_defaults(func=lambda args: delete_datajob_cmd(args, client_from_args(args)))

    start_job = subparsers.add_parser("start-job", aliases=["job-start"], help="Start data job.")
    add_common(start_job)
    start_job.add_argument("--job-id", required=True)
    start_job.add_argument("--job-name", help="Avoid an extra query when known.")
    start_job.add_argument("--dry-run", action="store_true")
    start_job.set_defaults(func=lambda args: start_datajob_cmd(args, client_from_args(args)))

    stop_job = subparsers.add_parser("stop-job", aliases=["job-stop"], help="Stop data job.")
    add_common(stop_job)
    stop_job.add_argument("--job-id", required=True)
    stop_job.add_argument("--job-name", help="Avoid an extra query when known.")
    stop_job.add_argument("--dry-run", action="store_true")
    stop_job.set_defaults(func=lambda args: stop_datajob_cmd(args, client_from_args(args)))

    restart_job = subparsers.add_parser("restart-job", aliases=["job-restart"], help="Restart data job.")
    add_common(restart_job)
    restart_job.add_argument("--job-id", required=True)
    restart_job.add_argument("--job-name", help="Avoid an extra query when known.")
    restart_job.add_argument("--dry-run", action="store_true")
    restart_job.set_defaults(func=lambda args: restart_datajob_cmd(args, client_from_args(args)))

    replay_job = subparsers.add_parser("replay-job", aliases=["job-replay", "rerun-job", "job-rerun"], help="Replay/rerun data job from start.")
    add_common(replay_job)
    replay_job.add_argument("--job-id", required=True)
    replay_job.add_argument("--job-name", help="Avoid an extra query when known.")
    replay_job.add_argument("--dry-run", action="store_true")
    replay_job.set_defaults(func=lambda args: replay_datajob_cmd(args, client_from_args(args)))

    continue_job = subparsers.add_parser(
        "continue-job",
        aliases=["job-continue", "active-fsm-job", "job-active-fsm"],
        help="Activate an inactive INIT job using frontend fsmStart; BUILD_STRUCT, when present, must be COMPLETE.",
    )
    add_common(continue_job)
    continue_job.add_argument("--job-id", required=True)
    continue_job.add_argument("--job-name", help="Avoid an extra query when known.")
    continue_job.add_argument("--dry-run", action="store_true")
    continue_job.set_defaults(func=lambda args: active_fsm_datajob_cmd(args, client_from_args(args)))

    list_fsm = subparsers.add_parser("list-fsm", aliases=["fsm-list"], help="List FSM records like the CloudCanal system FSM page.")
    add_common(list_fsm)
    list_fsm.add_argument("--job-id", help="Resolve dataJobName from a job and filter FSM list.")
    list_fsm.add_argument("--job-name", help="Filter by dataJobName.")
    list_fsm.add_argument("--state", default="all", help="Filter dataTaskState; use all for frontend default.")
    list_fsm.add_argument("--payload-json", help="Raw FSM list payload JSON or @file; merged first.")
    list_fsm.add_argument("--dry-run", action="store_true")
    list_fsm.set_defaults(func=lambda args: list_fsm_cmd(args, client_from_args(args)))

    query_fsm = subparsers.add_parser("query-fsm", aliases=["fsm-query"], help="Query FSM detail by fsm id or job id.")
    add_common(query_fsm)
    query_fsm.add_argument("--fsm-id")
    query_fsm.add_argument("--job-id")
    query_fsm.add_argument("--job-name", help="Avoid an extra query/list lookup when known.")
    query_fsm.add_argument("--payload-json", help="Raw FSM detail payload JSON or @file; merged first.")
    query_fsm.add_argument("--dry-run", action="store_true")
    query_fsm.set_defaults(func=lambda args: query_fsm_cmd(args, client_from_args(args)))

    activate_fsm = subparsers.add_parser("activate-fsm", aliases=["fsm-activate"], help="Activate an FSM from the CloudCanal system FSM page.")
    add_common(activate_fsm)
    activate_fsm.add_argument("--fsm-id")
    activate_fsm.add_argument("--job-id")
    activate_fsm.add_argument("--job-name", help="Resolve fsm id by data job name if --fsm-id is omitted.")
    activate_fsm.add_argument("--dry-run", action="store_true")
    activate_fsm.set_defaults(func=lambda args: activate_fsm_cmd(args, client_from_args(args)))

    inactivate_fsm = subparsers.add_parser("inactivate-fsm", aliases=["fsm-inactivate", "deactivate-fsm"], help="Inactivate an FSM from the CloudCanal system FSM page.")
    add_common(inactivate_fsm)
    inactivate_fsm.add_argument("--fsm-id")
    inactivate_fsm.add_argument("--job-id")
    inactivate_fsm.add_argument("--job-name", help="Resolve fsm id by data job name if --fsm-id is omitted.")
    inactivate_fsm.add_argument("--dry-run", action="store_true")
    inactivate_fsm.set_defaults(func=lambda args: inactivate_fsm_cmd(args, client_from_args(args)))

    operate_jobs = subparsers.add_parser("operate-jobs", aliases=["jobs-op"], help="Batch start/stop/restart/continue jobs; replay loops single-job API.")
    add_common(operate_jobs)
    operate_jobs.add_argument("--action", required=True, choices=("start", "stop", "restart", "replay", "active-fsm"))
    operate_jobs.add_argument("--job-id", action="append", required=True, help="Job id or comma-separated job ids. May repeat.")
    operate_jobs.add_argument("--dry-run", action="store_true")
    operate_jobs.set_defaults(func=lambda args: operate_datajobs_cmd(args, client_from_args(args)))

    precheck_parser = subparsers.add_parser("precheck", aliases=["job-precheck"], help="Run a frontend data-job precheck stage with raw payload JSON.")
    add_common(precheck_parser)
    precheck_parser.add_argument("--stage", required=True, choices=("first", "step-two", "step-three", "obj-necessary", "final"))
    precheck_parser.add_argument("--payload-json", help="DataJobData JSON or @file. Empty for first stage.")
    precheck_parser.set_defaults(func=lambda args: precheck_cmd(args, client_from_args(args)))

    update_desc = subparsers.add_parser("update-job-desc", aliases=["job-update-desc"], help="Update data job description.")
    add_common(update_desc)
    update_desc.add_argument("--job-id", required=True)
    update_desc.add_argument("--desc", required=True)
    update_desc.add_argument("--dry-run", action="store_true")
    update_desc.set_defaults(func=lambda args: update_job_desc_cmd(args, client_from_args(args)))

    update_level = subparsers.add_parser("update-job-level", aliases=["job-update-level"], help="Update data job level, e.g. P1/P2/P3/P4.")
    add_common(update_level)
    update_level.add_argument("--job-id", required=True)
    update_level.add_argument("--level", required=True)
    update_level.add_argument("--dry-run", action="store_true")
    update_level.set_defaults(func=lambda args: update_job_level_cmd(args, client_from_args(args)))

    query_options = subparsers.add_parser("query-job-options", aliases=["job-options"], help="Query page options for a data job.")
    add_common(query_options)
    query_options.add_argument("--job-id", required=True)
    query_options.set_defaults(func=lambda args: query_job_options_cmd(args, client_from_args(args)))

    update_options = subparsers.add_parser("update-job-options", aliases=["job-update-options"], help="Update data job options.")
    add_common(update_options)
    update_options.add_argument("--job-id", required=True)
    update_options.add_argument("--options-json", help="Options map JSON or @file.")
    update_options.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="Option override. May repeat.")
    update_options.add_argument("--dry-run", action="store_true")
    update_options.set_defaults(func=lambda args: update_job_options_cmd(args, client_from_args(args)))

    update_transfer = subparsers.add_parser("update-transfer-object", aliases=["job-update-transfer-object"], help="Update job subscribe objects with raw UpdateTransferObjFO payload.")
    add_common(update_transfer)
    update_transfer.add_argument("--job-id", required=True)
    update_transfer.add_argument("--payload-json", required=True, help="UpdateTransferObjFO JSON or @file. Merged with dataJobId.")
    update_transfer.add_argument("--full", action="store_true", help="Use updatetransferobjectforfull endpoint.")
    update_transfer.add_argument("--dry-run", action="store_true")
    update_transfer.set_defaults(func=lambda args: update_transfer_object_cmd(args, client_from_args(args)))

    can_revise = subparsers.add_parser("can-add-revise-task", aliases=["job-can-add-revise"], help="Check whether a job can add a revise task.")
    add_common(can_revise)
    can_revise.add_argument("--job-id", required=True)
    can_revise.add_argument("--payload-json", help="Extra payload JSON or @file; merged last.")
    can_revise.add_argument("--dry-run", action="store_true")
    can_revise.set_defaults(func=lambda args: can_add_revise_task_cmd(args, client_from_args(args)))

    add_revise = subparsers.add_parser("add-revise-task", aliases=["job-add-revise"], help="Add a revise task for a job.")
    add_common(add_revise)
    add_revise.add_argument("--job-id", required=True)
    add_revise.add_argument("--payload-json", help="Extra payload JSON or @file; merged last.")
    add_revise.add_argument("--dry-run", action="store_true")
    add_revise.set_defaults(func=lambda args: add_revise_task_cmd(args, client_from_args(args)))

    add_check_child = subparsers.add_parser("add-check-child-job", aliases=["job-add-check-child"], help="Add a check child job.")
    add_common(add_check_child)
    add_check_child.add_argument("--job-id", required=True)
    add_check_child.add_argument("--check-period", action="store_true")
    add_check_child.add_argument("--check-period-cron-expr")
    add_check_child.add_argument("--check-once", action="store_true", default=True, help="Create a one-shot check child. Default true.")
    add_check_child.add_argument("--no-check-once", action="store_true", help="Disable one-shot check in the payload.")
    add_check_child.add_argument("--full-check", action="store_true", default=True, help="Run a full check. Default true.")
    add_check_child.add_argument("--no-full-check", action="store_true", help="Disable fullCheck in the payload.")
    add_check_child.add_argument("--payload-json", help="Extra AddCheckChildJob payload JSON or @file; merged last.")
    add_check_child.add_argument("--dry-run", action="store_true")
    add_check_child.set_defaults(func=lambda args: add_check_child_job_cmd(args, client_from_args(args)))

    edit_job = subparsers.add_parser("edit-job", aliases=["job-edit"], help="Build and submit frontend-aligned modify-subscription payload.")
    add_job_common(edit_job)
    edit_job.add_argument("--job-id", required=True)
    edit_job.add_argument("--source-type", help="Override source datasource type.")
    edit_job.add_argument("--target-type", help="Override target datasource type.")
    edit_job.add_argument("--source-host-type", choices=("private", "public", "PRIVATE", "PUBLIC"))
    edit_job.add_argument("--target-host-type", choices=("private", "public", "PRIVATE", "PUBLIC"))
    edit_job.add_argument("--source-db")
    edit_job.add_argument("--source-schema")
    edit_job.add_argument("--target-db")
    edit_job.add_argument("--target-schema")
    edit_job.add_argument("--target-table")
    edit_job.add_argument("--add-table", action="append", default=[], help="Source table, or source=target. May repeat.")
    edit_job.add_argument("--add-table-map", action="append", default=[], help="Explicit source=target add-table mapping. May repeat.")
    edit_job.add_argument("--remove-table", action="append", default=[], help="Subscribed source table to remove from the job. May repeat.")
    edit_job.add_argument("--column-map", action="append", default=[], help="SRC=DST or TABLE:SRC=DST for added tables. May repeat.")
    edit_job.add_argument("--source-schema-without-add-json", help="Override srcSchemaWithoutAdd JSON or @file.")
    edit_job.add_argument("--target-schema-without-add-json", help="Override dstSchemaWithoutAdd JSON or @file.")
    edit_job.add_argument("--mapping-without-add-json", help="Override mappingConfigWithoutAdd JSON or @file.")
    edit_job.add_argument("--reduce-config-json", help="Raw reduceConfig sourceSchema JSON or @file for unsubscribe/reduce cases.")
    edit_job.add_argument("--payload-json", help="Raw UpdateTransferObjFO JSON or @file; merged last.")
    edit_job.add_argument("--processor-without-add-json", help="processorConfsWithoutAdd JSON or @file.")
    edit_job.add_argument("--add-processor-config-json", help="addProcessorConfs JSON or @file.")
    edit_job.add_argument("--table-rule", help="Override common table mapping rule for added tables.")
    edit_job.add_argument("--column-rule", help="Override common column mapping rule for added tables.")
    edit_job.add_argument("--table-mapping-method", help="Override added table mapping method.")
    edit_job.add_argument("--table-select-mode", default="LIST_ALL_AND_SELECT")
    edit_job.add_argument("--auto-create-target", action="store_true")
    edit_job.add_argument("--struct-migration", action="store_true")
    edit_job.add_argument("--initial-sync", action="store_true")
    edit_job.add_argument("--full", action="store_true", help="Use updatetransferobjectforfull endpoint.")
    edit_job.add_argument("--dry-run", action="store_true")
    edit_job.set_defaults(func=lambda args: edit_job_cmd(args, client_from_args(args)))

    merge_edit = subparsers.add_parser("manual-merge-edit-job", aliases=["job-manual-merge-edit"], help="Manually merge an edited job.")
    add_common(merge_edit)
    merge_edit.add_argument("--job-id", required=True)
    merge_edit.add_argument("--dry-run", action="store_true")
    merge_edit.set_defaults(func=lambda args: manual_merge_edit_job_cmd(args, client_from_args(args)))

    attach_incre = subparsers.add_parser("attach-incre-task", aliases=["job-attach-incre"], help="Attach an incremental task.")
    add_common(attach_incre)
    attach_incre.add_argument("--job-id", required=True)
    attach_incre.add_argument("--payload-json", help="Extra payload JSON or @file; merged last.")
    attach_incre.add_argument("--dry-run", action="store_true")
    attach_incre.set_defaults(func=lambda args: attach_incre_task_cmd(args, client_from_args(args)))

    detach_incre = subparsers.add_parser("detach-incre-task", aliases=["job-detach-incre"], help="Detach an incremental task.")
    add_common(detach_incre)
    detach_incre.add_argument("--job-id", required=True)
    detach_incre.add_argument("--payload-json", help="Extra payload JSON or @file; merged last.")
    detach_incre.add_argument("--dry-run", action="store_true")
    detach_incre.set_defaults(func=lambda args: detach_incre_task_cmd(args, client_from_args(args)))

    migration_tip = subparsers.add_parser("generate-migration-tip", aliases=["job-migration-tip"], help="Generate migration tip with frontend payload fields.")
    add_common(migration_tip)
    migration_tip.add_argument("--job-id")
    migration_tip.add_argument("--source-type")
    migration_tip.add_argument("--target-type")
    migration_tip.add_argument("--source-ds-id")
    migration_tip.add_argument("--target-ds-id")
    migration_tip.add_argument("--payload-json", help="Raw GenerateMigrationTip payload JSON or @file; merged last.")
    migration_tip.add_argument("--dry-run", action="store_true")
    migration_tip.set_defaults(func=lambda args: generate_migration_tip_cmd(args, client_from_args(args)))

    time_schedule = subparsers.add_parser("time-schedule", aliases=["job-time-schedule"], help="Pause/resume/start a time-schedule job.")
    add_common(time_schedule)
    time_schedule.add_argument("--action", required=True, choices=("pause", "resume", "start"))
    time_schedule.add_argument("--job-id", required=True)
    time_schedule.add_argument("--dry-run", action="store_true")
    time_schedule.set_defaults(func=lambda args: time_schedule_cmd(args, client_from_args(args)))

    manual_schedule = subparsers.add_parser("manual-schedule", aliases=["task-manual-schedule"], help="Manually schedule one or more data tasks to a worker.")
    add_common(manual_schedule)
    manual_schedule.add_argument("--data-task-id", action="append", required=True, help="Task id or comma-separated task ids. May repeat.")
    manual_schedule.add_argument("--old-worker-id", required=True)
    manual_schedule.add_argument("--target-worker-id", required=True)
    manual_schedule.add_argument("--dry-run", action="store_true")
    manual_schedule.set_defaults(func=lambda args: manual_schedule_cmd(args, client_from_args(args)))

    specs = subparsers.add_parser("list-job-specs", aliases=["job-specs"], help="List available task specs.")
    add_job_common(specs)
    specs.add_argument("--mode", default="full-sync", choices=("full", "migration", "full-sync", "sync", "increment", "incremental", "check", "struct"))
    specs.add_argument("--job-type", choices=("MIGRATION", "SYNC", "CHECK", "STRUCT_MIGRATION"))
    specs.add_argument("--struct-migration", dest="struct_migration", action="store_true", default=None)
    specs.add_argument("--no-struct-migration", dest="struct_migration", action="store_false")
    specs.set_defaults(func=lambda args: list_specs_cmd(args, client_from_args(args)))

    extra_configs = subparsers.add_parser("job-extra-configs", help="Query dynamic extra job configs.")
    add_common(extra_configs)
    extra_configs.add_argument("--source-type")
    extra_configs.add_argument("--target-type")
    extra_configs.add_argument("--source-ds-id")
    extra_configs.add_argument("--target-ds-id")
    extra_configs.add_argument("--defaults", action="store_true", help="Print default extra-json payload only.")
    extra_configs.set_defaults(func=lambda args: job_extra_configs_cmd(args, client_from_args(args)))

    list_dbs = subparsers.add_parser("list-dbs", help="List datasource db/schema names.")
    add_job_common(list_dbs)
    list_dbs.add_argument("--data-source-id", required=True)
    list_dbs.add_argument("--host")
    list_dbs.add_argument("--host-type", choices=("private", "public", "PRIVATE", "PUBLIC"))
    list_dbs.set_defaults(func=lambda args: list_dbs_cmd(args, client_from_args(args)))

    list_tables = subparsers.add_parser("list-tables", help="List datasource tables.")
    add_job_common(list_tables)
    list_tables.add_argument("--data-source-id", required=True)
    list_tables.add_argument("--db", required=True)
    list_tables.add_argument("--schema")
    list_tables.add_argument("--host")
    list_tables.add_argument("--host-type", choices=("private", "public", "PRIVATE", "PUBLIC"))
    list_tables.add_argument("--table-select-mode", default="LIST_ALL_AND_SELECT")
    list_tables.set_defaults(func=lambda args: list_tables_cmd(args, client_from_args(args)))

    list_columns = subparsers.add_parser("list-columns", help="List datasource columns for selected tables.")
    add_job_common(list_columns)
    list_columns.add_argument("--data-source-id", required=True)
    list_columns.add_argument("--db")
    list_columns.add_argument("--schema")
    list_columns.add_argument("--table", action="append", required=True, help="Table name or db.schema.table. May repeat.")
    list_columns.add_argument("--host")
    list_columns.add_argument("--host-type", choices=("private", "public", "PRIVATE", "PUBLIC"))
    list_columns.set_defaults(func=lambda args: list_columns_cmd(args, client_from_args(args)))

    list_uniqs = subparsers.add_parser("list-table-uniqs", help="List datasource unique key metadata for selected tables.")
    add_job_common(list_uniqs)
    list_uniqs.add_argument("--data-source-id", required=True)
    list_uniqs.add_argument("--db", action="append", required=True, help="Database/schema name. May repeat.")
    list_uniqs.add_argument("--host")
    list_uniqs.add_argument("--host-type", choices=("private", "public", "PRIVATE", "PUBLIC"))
    list_uniqs.set_defaults(func=lambda args: list_table_uniqs_cmd(args, client_from_args(args)))

    type_mapping = subparsers.add_parser("type-mapping", help="Query source-to-target field type mapping.")
    add_common(type_mapping)
    type_mapping.add_argument("--source-type")
    type_mapping.add_argument("--target-type")
    type_mapping.add_argument("--source-ds-id")
    type_mapping.add_argument("--target-ds-id")
    type_mapping.set_defaults(func=lambda args: type_mapping_cmd(args, client_from_args(args)))

    get_config = subparsers.add_parser("get-job-config", aliases=["job-config-get"], help="Get all configs for a data job.")
    add_common(get_config)
    get_config.add_argument("--job-id", required=True)
    get_config.set_defaults(func=lambda args: get_job_config_cmd(args, client_from_args(args)))

    list_config_tags = subparsers.add_parser("list-job-config-tags", aliases=["job-config-tags"], help="List data job config tags.")
    add_common(list_config_tags)
    list_config_tags.set_defaults(func=lambda args: list_job_config_tags_cmd(args, client_from_args(args)))

    list_config = subparsers.add_parser("list-job-configs", aliases=["job-configs"], help="List data job configs by name/tag.")
    add_common(list_config)
    list_config.add_argument("--job-id", required=True)
    list_config.add_argument("--config-name")
    list_config.add_argument("--tag", action="append", default=[], help="ConfigTagType. May repeat.")
    list_config.add_argument("--payload-json", help="Raw ListJobConfigsFO JSON or @file; merged last.")
    list_config.set_defaults(func=lambda args: list_job_configs_cmd(args, client_from_args(args)))

    update_config = subparsers.add_parser("update-job-configs", aliases=["job-config-update"], help="Update data job configs.")
    add_common(update_config)
    update_config.add_argument("--job-id", required=True)
    update_config.add_argument("--payload-json", help="Raw list of UpdateJobConfigFO JSON or @file.")
    update_config.add_argument("--config", action="append", default=[], metavar="NAME:ENDPOINT:TYPE:VALUE", help="Config item. May repeat.")
    update_config.add_argument("--need-create", action="store_true")
    update_config.add_argument("--dry-run", action="store_true")
    update_config.set_defaults(func=lambda args: update_job_configs_cmd(args, client_from_args(args)))

    export_config = subparsers.add_parser("export-job-config", aliases=["job-config-export"], help="Export data job configs.")
    add_common(export_config)
    export_config.add_argument("--job-id", required=True)
    export_config.add_argument("--export-type", default="EXCEL")
    export_config.add_argument("--payload-json", help="Raw export payload JSON or @file; merged last.")
    export_config.add_argument("--dry-run", action="store_true")
    export_config.set_defaults(func=lambda args: export_job_config_cmd(args, client_from_args(args)))

    config_template = subparsers.add_parser("job-config-template", help="Preview/apply a data job config template.")
    add_common(config_template)
    config_template.add_argument("--job-id", required=True)
    config_template.add_argument("--template-id", required=True)
    config_template.add_argument("--preview", action="store_true")
    config_template.add_argument("--dry-run", action="store_true")
    config_template.set_defaults(func=lambda args: job_config_template_cmd(args, client_from_args(args)))

    position_ops = subparsers.add_parser("position-ops", help="Query dynamic update-position form ops for an incremental task.")
    add_common(position_ops)
    position_ops.add_argument("--task-id", required=True)
    position_ops.add_argument("--source-type", help="Source datasource type.")
    position_ops.add_argument("--job-id", help="Infer source type from job when --source-type is omitted.")
    position_ops.set_defaults(func=lambda args: position_ops_cmd(args, client_from_args(args)))

    fetch_pos = subparsers.add_parser("fetch-current-pos", aliases=["position-fetch-current"], help="Fetch current position for a task and position type.")
    add_common(fetch_pos)
    fetch_pos.add_argument("--task-id", required=True)
    fetch_pos.add_argument("--pos-type", required=True, help="IncrePosType, e.g. MYSQL_LOG_FILE_POS/TIDB_TIMESTAMP_POS/PG_LSN_POS.")
    fetch_pos.set_defaults(func=lambda args: fetch_current_pos_cmd(args, client_from_args(args)))

    update_pos = subparsers.add_parser("update-incre-pos", aliases=["position-update"], help="Update incremental task position. Task must be STOP.")
    add_common(update_pos)
    update_pos.add_argument("--task-id", required=True)
    update_pos.add_argument("--pos-type", required=True)
    update_pos.add_argument("--journal-file")
    update_pos.add_argument("--file-position", type=int)
    update_pos.add_argument("--gtid-position")
    update_pos.add_argument("--position-timestamp", type=int)
    update_pos.add_argument("--server-id", type=int)
    update_pos.add_argument("--lsn")
    update_pos.add_argument("--scn", type=int)
    update_pos.add_argument("--scn-index", type=int)
    update_pos.add_argument("--common-pos-str", help="Raw commonPosStr or @file.")
    update_pos.add_argument("--data-id", type=int)
    update_pos.add_argument("--transaction-id", type=int)
    update_pos.add_argument("--payload-json", help="Raw UpdateIncrePosFO JSON or @file; merged last.")
    update_pos.add_argument("--dry-run", action="store_true")
    update_pos.set_defaults(func=lambda args: update_incre_pos_cmd(args, client_from_args(args)))

    reset_current = subparsers.add_parser("reset-pos-to-current", aliases=["position-reset-current"], help="Reset incremental task positions to current.")
    add_common(reset_current)
    reset_current.add_argument("--task-id", required=True)
    reset_current.add_argument("--pos-type", action="append", required=True, help="IncrePosType. May repeat.")
    reset_current.add_argument("--dry-run", action="store_true")
    reset_current.set_defaults(func=lambda args: reset_pos_to_current_cmd(args, client_from_args(args)))

    reset_pos = subparsers.add_parser("reset-position", aliases=["position-reset"], help="Reset task position by time.")
    add_common(reset_pos)
    reset_pos.add_argument("--task-id", required=True)
    reset_pos.add_argument("--reset-time-millis", required=True)
    reset_pos.add_argument("--clear-position", action="store_true")
    reset_pos.add_argument("--verify-code")
    reset_pos.add_argument("--data-id", type=int)
    reset_pos.add_argument("--payload-json", help="Raw ResetPositionFO JSON or @file; merged last.")
    reset_pos.add_argument("--dry-run", action="store_true")
    reset_pos.set_defaults(func=lambda args: reset_position_cmd(args, client_from_args(args)))
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except (ApiError, ValueError, KeyboardInterrupt) as e:
        print("ERROR: " + str(e), file=sys.stderr)
        return 1
