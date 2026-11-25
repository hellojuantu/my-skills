import json
import re
import time
from types import SimpleNamespace

from cc_console.client import ApiError, json_part
from cc_console.clusters import resolve_cluster_id
from cc_console.consolejob import console_job_failure_summary, query_console_job
from cc_console.datasource import choose_test_host, normalize_ds_type, normalize_host_type, query_datasource, query_datasource_config
from cc_console.utils import mask_payload, maybe_read_value_file, parse_int, print_json


CREATE_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/create"
DELETE_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/delete"
QUERY_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/queryjob"
QUERY_JOB_SCHEMA_PATH = "/cloudcanal/console/api/v1/inner/datajob/queryjobschemabyid"
LIST_CHECK_TASKS_PATH = "/cloudcanal/console/api/v1/inner/datajob/listchecktasks"
LIST_JOBS_BY_PAGE_PATH = "/cloudcanal/console/api/v1/inner/datajob/listbypage"
LIST_JOBS_SIMPLE_PATH = "/cloudcanal/console/api/v1/inner/datajob/listsimpleforsearch"
START_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/start"
STOP_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/stop"
RESTART_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/restart"
REPLAY_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/replay"
ACTIVE_FSM_PATH = "/cloudcanal/console/api/v1/inner/datajob/activefsm"
ACTIVE_FSM_BATCH_PATH = "/cloudcanal/console/api/v1/inner/datajob/activefsmbatch"
FSM_LIST_PATH = "/cloudcanal/console/api/v1/inner/fsm/list"
FSM_DETAIL_PATH = "/cloudcanal/console/api/v1/inner/fsm/detail"
FSM_ACTIVATE_PATH = "/cloudcanal/console/api/v1/inner/fsm/activate"
FSM_INACTIVATE_PATH = "/cloudcanal/console/api/v1/inner/fsm/inactivate"
GET_FOLLOWED_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/getfollowedjob"
CAN_ADD_REVISE_TASK_PATH = "/cloudcanal/console/api/v1/inner/datajob/canaddrevisetask"
ADD_REVISE_TASK_PATH = "/cloudcanal/console/api/v1/inner/datajob/addrevisetask"
ADD_CHECK_CHILD_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/addcheckchildjob"
DETACH_INCRE_TASK_PATH = "/cloudcanal/console/api/v1/inner/datajob/detachincretask"
ATTACH_INCRE_TASK_PATH = "/cloudcanal/console/api/v1/inner/datajob/attachincretask"
GENERATE_MIGRATION_TIP_PATH = "/cloudcanal/console/api/v1/inner/datajob/generateMigrationTip"
START_BATCH_PATH = "/cloudcanal/console/api/v1/inner/datajob/startbatch"
STOP_BATCH_PATH = "/cloudcanal/console/api/v1/inner/datajob/stopbatch"
RESTART_BATCH_PATH = "/cloudcanal/console/api/v1/inner/datajob/restartbatch"
UPDATE_DESC_PATH = "/cloudcanal/console/api/v1/inner/datajob/updatedesc"
UPDATE_LEVEL_PATH = "/cloudcanal/console/api/v1/inner/datajob/updatelevel"
QUERY_JOB_OPTIONS_PATH = "/cloudcanal/console/api/v1/inner/datajob/queryjoboptions"
UPDATE_JOB_OPTIONS_PATH = "/cloudcanal/console/api/v1/inner/datajob/updatejoboptions"
UPDATE_TRANSFER_OBJECT_PATH = "/cloudcanal/console/api/v1/inner/datajob/updatetransferobject"
UPDATE_TRANSFER_OBJECT_FOR_FULL_PATH = "/cloudcanal/console/api/v1/inner/datajob/updatetransferobjectforfull"
MANUAL_MERGE_EDIT_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/manualmergeeditjob"
PAUSE_TIME_SCHEDULE_PATH = "/cloudcanal/console/api/v1/inner/datajob/pausetimeschedule"
RESUME_TIME_SCHEDULE_PATH = "/cloudcanal/console/api/v1/inner/datajob/resumetimeschedule"
START_TIME_SCHEDULE_JOB_PATH = "/cloudcanal/console/api/v1/inner/datajob/starttimeschedulejob"
MANUAL_SCHEDULE_PATH = "/cloudcanal/console/api/v1/inner/schedule/manualschedule"
MANUAL_BATCH_SCHEDULE_PATH = "/cloudcanal/console/api/v1/inner/schedule/manualbatchschedule"
POSITION_RESET_PATH = "/cloudcanal/console/api/v1/inner/position/reset"
POSITION_RESET_POS_TO_CURRENT_PATH = "/cloudcanal/console/api/v1/inner/position/resetpostocurrent"
POSITION_UPDATE_INCRE_POS_PATH = "/cloudcanal/console/api/v1/inner/position/updateincrepos"
POSITION_FETCH_CURRENT_POS_PATH = "/cloudcanal/console/api/v1/inner/position/fetchcurrentpos"
JOB_CONFIG_GET_PATH = "/cloudcanal/console/api/v1/inner/datajob/config/get"
JOB_CONFIG_LIST_TAG_PATH = "/cloudcanal/console/api/v1/inner/datajob/config/list/tag"
JOB_CONFIG_LIST_PATH = "/cloudcanal/console/api/v1/inner/datajob/config/listconfigs"
JOB_CONFIG_UPDATE_PATH = "/cloudcanal/console/api/v1/inner/datajob/config/update"
JOB_CONFIG_TEMPLATE_UPDATE_PATH = "/cloudcanal/console/api/v1/inner/datajob/config/updatebytemplate"
JOB_CONFIG_TEMPLATE_PREVIEW_PATH = "/cloudcanal/console/api/v1/inner/datajob/config/updatebytemplate/preview"
JOB_CONFIG_EXPORT_PATH = "/cloudcanal/console/api/v1/inner/datajob/config/export"
PRECHECK_FIRST_PATH = "/cloudcanal/console/api/v1/inner/datajob/precheck/first"
PRECHECK_STEP_TWO_PATH = "/cloudcanal/console/api/v1/inner/datajob/precheck/steptwo"
PRECHECK_STEP_THREE_PATH = "/cloudcanal/console/api/v1/inner/datajob/precheck/stepthree"
PRECHECK_FINAL_PATH = "/cloudcanal/console/api/v1/inner/datajob/precheck/final"
PRECHECK_OBJ_NECESSARY_PATH = "/cloudcanal/console/api/v1/inner/datajob/precheck/objNecessary"
LIST_SPECS_PATH = "/cloudcanal/console/api/v1/inner/spec/listspecs"
TRANSFORM_JOB_TYPE_PATH = "/cloudcanal/console/api/v1/inner/constant/transformjobtype"
SCHEMA_MAPPING_RULE_PATH = "/cloudcanal/console/api/v1/inner/constant/ds/schemamappingrule"
TABLE_MAPPING_RULE_PATH = "/cloudcanal/console/api/v1/inner/constant/ds/tablemappingrule"
COLUMN_MAPPING_RULE_PATH = "/cloudcanal/console/api/v1/inner/constant/ds/columnmappingrule"
DS_CHARSET_OPTIONS_PATH = "/cloudcanal/console/api/v1/inner/constant/dscharset/dscharsetoptions"
LIST_DB_PATH = "/cloudcanal/console/api/v1/inner/datasource/db/list"
LIST_TABLE_NEW_PATH = "/cloudcanal/console/api/v1/inner/datasource/table/listNew"
LIST_DB_TABLES_UNIQS_PATH = "/cloudcanal/console/api/v1/inner/datasource/listdbtablesuniqs"
COLUMN_BATCH_LIST_PATH = "/cloudcanal/console/api/v1/inner/datasource/column/batchlist"
TYPE_MAPPING_PATH = "/cloudcanal/console/api/v1/inner/datasource/gettypemapping"
WEBOP_EXTRA_CONFIGS_PATH = "/cloudcanal/console/api/v1/inner/webop/extraconfigs"
WEBOP_INCRE_DATA_TASK_POS_OPS_PATH = "/cloudcanal/console/api/v1/inner/webop/incredatataskposops"

MQ_TYPES = {"Kafka", "AmazonMSK", "RocketMQ", "RabbitMQ", "AutoMQ", "Pulsar"}
KAFKA_TYPES = {"Kafka", "AutoMQ", "AmazonMSK"}
ROCKETMQ_TYPES = {"RocketMQ"}
RABBITMQ_TYPES = {"RabbitMQ"}
PULSAR_TYPES = {"Pulsar"}
TUNNEL_TYPES = {"Tunnel"}
REDIS_TYPES = {"Redis", "ElastiCache"}
SEARCH_TYPES = {"ElasticSearch"}
ORACLE_TYPES = {"Oracle"}
KUDU_TYPES = {"Kudu"}
DYNAMODB_TYPES = {"DynamoDB"}
RAG_API_TYPES = {"RagApi"}
DRDS_TYPES = {"DRDS", "PolarDbX"}
TDSQL_MYSQL_TYPES = {"TdsqlMySQL"}
HIVE_TYPES = {"Hive"}
GREPTIME_TYPES = {"GreptimeDB"}
PARTITION_EXPR_TYPES = {"StarRocks", "Doris", "SelectDB", "Iceberg", "Paimon", "DeltaLake"}
DATASOURCE_TASK_CONFIG_NAMES = {
    "TiDB": {"pdHost"},
    "StarRocks": {"privateHttpHost", "publicHttpHost", "feHttpAddr", "beThriftAddr"},
    "Doris": {"privateHttpHost", "publicHttpHost", "feHttpAddr", "beThriftAddr"},
    "SelectDB": {"privateHttpHost", "publicHttpHost", "feHttpAddr", "beThriftAddr"},
}
PROXY_TASK_CONFIG_NAMES = {"proxyMode", "remoteProxyIp", "remoteProxyPort", "remoteProxyAccount", "remoteProxyPwd"}
NO_COLUMN_TYPES = MQ_TYPES | REDIS_TYPES | SEARCH_TYPES | {"MongoDB", "DocumentDB", "Kudu", "RagApi", "DynamoDB"}
NO_DB_TYPES = KUDU_TYPES | MQ_TYPES | REDIS_TYPES | SEARCH_TYPES | RAG_API_TYPES | DYNAMODB_TYPES
HAS_SCHEMA_TYPES = {
    "Tunnel",
    "Hudi",
    "Oracle",
    "Hana",
    "PostgreSQL",
    "PolarDBPg",
    "Redshift",
    "GaussDBForOpenGauss",
    "AuroraPostgreSQL",
    "Greenplum",
    "SQLServer",
    "Db2",
    "OssFile",
    "S3File",
    "SshFile",
    "GoogleDrive",
    "GaussDB",
    "Yuque",
    "KingbaseES",
    "Vastbase",
    "Hologres",
    "Snowflake",
    "Cloudberry",
}
NONE_SCHEMA_TYPES = NO_DB_TYPES


def read_json_arg(value, default=None):
    if value in (None, ""):
        return default
    text = maybe_read_value_file(value)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("invalid JSON: " + str(e)) from e


def deep_merge(base, extra):
    if not extra:
        return base
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def success_data(client, response, action):
    data = client.ensure_success(response, action)
    return data


def data_source_type(ds):
    value = ds.get("dataSourceType")
    if not value:
        raise ValueError("datasource type not found in query response")
    return normalize_ds_type(str(value))


def host_type_value(value, fallback="PRIVATE"):
    return normalize_host_type(value) or fallback


def schema_level(ds_type, rule, side):
    key = "srcSchemaLevel" if side == "source" else "dstSchemaLevel"
    if rule and rule.get(key):
        return rule.get(key)
    if ds_type in NONE_SCHEMA_TYPES:
        return "NONE"
    if ds_type in HAS_SCHEMA_TYPES:
        return "DB_SCHEMA"
    return "SCHEMA"


def list_specs(client, job_type, initial_sync=False, short_term_sync=False):
    payload = {
        "dataJobType": job_type,
        "initialSync": bool(initial_sync),
        "shortTermSync": bool(short_term_sync),
    }
    response = client.post_json(LIST_SPECS_PATH, payload)
    return success_data(client, response, "list specs") or []


def resolve_spec_id(args, client, job_type, initial_sync, short_term_sync):
    if args.spec_id:
        return parse_int(args.spec_id, "specId")
    specs = list_specs(client, job_type, initial_sync, short_term_sync)
    if not specs:
        raise ApiError("list specs returned empty data")
    for spec in specs:
        if int(spec.get("id") or 0) == 15:
            return 15
    return parse_int(specs[0].get("id"), "specId")


def query_default_charset(client, ds_type):
    response = client.post_json(DS_CHARSET_OPTIONS_PATH, {"dataSourceType": ds_type})
    options = success_data(client, response, "query datasource charset options") or {}
    if isinstance(options, dict):
        options = options.get("dsCharsetOptions") or []
    for option in options:
        if option.get("defaultChecked") and option.get("dsCharset"):
            return option.get("dsCharset")
    if options and options[0].get("dsCharset"):
        return options[0].get("dsCharset")
    return "utf8"


def fetch_schema_mapping_rule(client, src_type, dst_type, dst_deploy_type=None):
    payload = {
        "srcDsType": src_type,
        "dstDsType": dst_type,
    }
    if dst_deploy_type:
        payload["dstDeployEnvType"] = dst_deploy_type
    response = client.post_json(SCHEMA_MAPPING_RULE_PATH, payload)
    return success_data(client, response, "query schema mapping rule") or {}


def fetch_table_mapping_rules(client, cluster_id, src_type, dst_type, dst_ds_id, dst_host_type, table_select_mode):
    payload = {
        "clusterId": cluster_id,
        "srcDsType": src_type,
        "dstDsType": dst_type,
        "dstDsId": dst_ds_id,
        "dstHostType": dst_host_type,
        "tableSelectMode": table_select_mode,
    }
    response = client.post_json(TABLE_MAPPING_RULE_PATH, payload)
    return success_data(client, response, "query table mapping rules") or []


def fetch_column_mapping_rules(client, src_type, dst_type):
    response = client.post_json(COLUMN_MAPPING_RULE_PATH, {"srcDsType": src_type, "dstDsType": dst_type})
    return success_data(client, response, "query column mapping rules") or []


def choose_default_rule(rules, fallback="MIRROR"):
    for rule in rules or []:
        if rule.get("defaultCheck") and rule.get("rule"):
            return rule.get("rule")
    for rule in rules or []:
        if rule.get("rule"):
            return rule.get("rule")
    return fallback


def transform_name(name, rule):
    if name is None:
        return None
    if rule == "TO_LOWER_CASE":
        return name.lower()
    if rule == "TO_UPPER_CASE":
        return name.upper()
    if rule == "TO_CAMEL_FORMAT":
        parts = [p for p in name.split("_") if p != ""]
        if not parts:
            return name
        return parts[0].lower() + "".join(p[:1].upper() + p[1:].lower() for p in parts[1:])
    if rule == "TO_UNDERLINE_FORMAT":
        return re.sub(r"(?<!^)([A-Z])", r"_\1", name).lower()
    return name


def compare_obj(value, parent=None):
    result = {"value": value}
    if parent is not None:
        result["parent"] = parent
    return result


def compare_obj_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def level_mapping(method, common_rule=None):
    result = {
        "method": method,
        "serializeMapping": {},
        "serializeAutoGenRules": {},
    }
    if common_rule:
        result["commonGenRule"] = common_rule
    return result


def add_mapping(mapping, src_obj, dst_obj):
    mapping["serializeMapping"][compare_obj_json(src_obj)] = compare_obj_json(dst_obj)


def split_table_ref(value):
    parts = value.split(".")
    if len(parts) == 1:
        return None, None, parts[0]
    if len(parts) == 2:
        return parts[0], None, parts[1]
    return ".".join(parts[:-2]), parts[-2], parts[-1]


def parse_table_path(value, level, default_db=None, default_schema=None):
    db_name, schema_name, table_name = split_table_ref(value)
    if not table_name:
        raise ValueError("table name is empty: " + value)
    if level == "DB_SCHEMA":
        return {
            "db": db_name or default_db,
            "schema": schema_name or default_schema,
            "table": table_name,
        }
    if level == "SCHEMA":
        return {
            "db": None,
            "schema": db_name or default_schema or default_db,
            "table": table_name,
        }
    return {
        "db": db_name or default_db,
        "schema": schema_name or default_schema,
        "table": table_name,
    }


def explicit_table_pairs(args):
    pairs = []
    for item in args.table or []:
        if "=" in item:
            src, dst = item.split("=", 1)
            pairs.append((src.strip(), dst.strip()))
        else:
            pairs.append((item.strip(), None))
    for item in args.table_map or []:
        if "=" not in item:
            raise ValueError("--table-map expects source=target, got: " + item)
        src, dst = item.split("=", 1)
        pairs.append((src.strip(), dst.strip()))
    return pairs


def parse_table_args(args, src_level, dst_level, schema_rule, table_rule, target_names=None):
    pairs = explicit_table_pairs(args)
    if not pairs:
        raise ValueError("at least one --table or --table-map is required unless schema JSON is supplied")

    tables = []
    schema_auto_rule = schema_rule.get("mappingRule") or "MIRROR"
    for src_text, dst_text in pairs:
        src = parse_table_path(src_text, src_level, args.source_db, args.source_schema)
        if dst_text:
            dst = parse_table_path(dst_text, dst_level, args.target_db, args.target_schema)
        else:
            if dst_level == "SCHEMA":
                target_db = None
                target_schema = args.target_schema or args.target_db or transform_name(src.get("schema") or src.get("db"), schema_auto_rule)
            elif dst_level == "DB_SCHEMA":
                target_db = args.target_db or transform_name(src.get("db") or src.get("schema"), schema_auto_rule)
                target_schema = args.target_schema or transform_name(src.get("schema") or src.get("db"), schema_auto_rule)
            else:
                target_db = args.target_db or transform_name(src.get("db"), schema_auto_rule)
                target_schema = args.target_schema or transform_name(src.get("schema"), schema_auto_rule)
            source_table = src["table"]
            target_table = args.target_table or (target_names or {}).get(source_table) or transform_name(source_table, table_rule)
            dst = {"db": target_db, "schema": target_schema, "table": target_table}
        tables.append(
            {
                "sourceDb": src.get("db"),
                "sourceSchema": src.get("schema"),
                "sourceTable": src.get("table"),
                "targetDb": dst.get("db"),
                "targetSchema": dst.get("schema"),
                "targetTable": dst.get("table"),
                "columnMaps": [],
            }
        )
    return tables


def parse_column_maps(args, tables):
    for item in args.column_map or []:
        table_hint = None
        expr = item
        if ":" in item and "=" in item and item.index(":") < item.index("="):
            table_hint, expr = item.split(":", 1)
        if "=" not in expr:
            raise ValueError("--column-map expects SRC=DST or TABLE:SRC=DST, got: " + item)
        src_col, dst_col = expr.split("=", 1)
        src_col = src_col.strip()
        dst_col = dst_col.strip()
        matched = []
        for table in tables:
            names = {table.get("sourceTable"), table.get("targetTable")}
            if table_hint is None or table_hint in names:
                table["columnMaps"].append((src_col, dst_col))
                matched.append(table)
        if not matched:
            raise ValueError("--column-map table hint not found: " + table_hint)


def build_table_object(table_name, auto_create_target, columns=None, specified_pks=None):
    result = {
        "table": table_name,
        "pattern": "",
        "columns": columns or [],
        "actions": [],
        "blackActs": [],
        "inBlackList": False,
        "targetAutoCreate": bool(auto_create_target),
    }
    if specified_pks is not None:
        result["specifiedPks"] = specified_pks
    return result


def column_schema_object(column, auto_create_target=False):
    name = column.get("columnName")
    if not name:
        return None
    return {
        "column": name,
        "targetAutoCreate": bool(auto_create_target),
        "inBlackList": False,
    }


def table_column_meta_items(meta, table, source_level):
    meta_map = (meta or {}).get("tableMetaDataMap") or {}
    db_candidates = []
    if source_level == "DB_SCHEMA":
        db_candidates.extend([table.get("sourceDb"), table.get("sourceSchema")])
    else:
        db_candidates.extend([table.get("sourceSchema"), table.get("sourceDb")])
    table_name = table.get("sourceTable")
    for db_name in [item for item in db_candidates if item]:
        db_meta = meta_map.get(db_name)
        if isinstance(db_meta, dict) and table_name in db_meta:
            return db_meta.get(table_name) or []
    for db_meta in meta_map.values():
        if isinstance(db_meta, dict) and table_name in db_meta:
            return db_meta.get(table_name) or []
    return []


def enrich_source_columns(client, source_id, cluster_id, source_type, source_level, source_host_type, tables, auto_create_target):
    if source_type in NO_COLUMN_TYPES:
        return
    for table in tables:
        table_name = table.get("sourceTable")
        if not table_name:
            continue
        if source_level == "DB_SCHEMA":
            db_name = table.get("sourceDb")
            schema_name = table.get("sourceSchema")
        else:
            db_name = table.get("sourceSchema") or table.get("sourceDb")
            schema_name = None
        meta = list_columns(client, source_id, cluster_id, [table_name], db_name=db_name, schema_name=schema_name, host_type=source_host_type)
        columns = []
        for item in table_column_meta_items(meta, table, source_level):
            column = column_schema_object(item, auto_create_target)
            if column:
                columns.append(column)
        if columns:
            table["sourceColumns"] = columns


def without_none(value):
    return {key: item for key, item in value.items() if item is not None}


def build_mq_schema_object(ds_type, table, table_key, side, auto_create_target=False):
    table_name = table.get(table_key)
    if ds_type in RABBITMQ_TYPES:
        result = {"queue": table_name, "queuePattern": ""}
    else:
        result = {
            "topic": table_name,
            "topicPattern": "",
            "partitions": table.get("partitions"),
            "pulsarTopicPersistent": table.get("pulsarTopicPersistent"),
            "partitionKeys": table.get("partitionKeys"),
        }
    if side == "source":
        result["inBlackList"] = False
        result["targetAutoCreate"] = bool(auto_create_target or table.get("needAutoCreated"))
        if table.get("cols"):
            result["specifiedPks"] = table.get("cols")
    return without_none(result)


def build_es_schema_object(table, table_key, side, auto_create_target=False):
    result = {
        "indexName": table.get(table_key),
        "fields": table.get("fields") or [],
        "numberOfShards": table.get("shards"),
        "numberOfReplicas": table.get("replication"),
        "globalTimeZone": table.get("globalTimeZone"),
        "idFieldNames": table.get("idFieldNames") or [],
        "cycleField": table.get("cycleField"),
    }
    if side == "source":
        result["targetAutoCreate"] = bool(auto_create_target or table.get("needAutoCreated"))
    return without_none(result)


def build_schema_json(ds_type, level, tables, side, auto_create_target=False):
    if side not in ("source", "target"):
        raise ValueError("unsupported schema side: " + side)
    db_key = side + "Db"
    schema_key = side + "Schema"
    table_key = side + "Table"

    if ds_type in MQ_TYPES:
        return [build_mq_schema_object(ds_type, table, table_key, side, auto_create_target) for table in tables]
    if ds_type in REDIS_TYPES:
        if side == "target":
            return [{"prefix": table.get(table_key), "suffixFields": table.get("suffixFields") or []} for table in tables]
        return [{"keyPrefix": table.get(table_key)} for table in tables]
    if ds_type in SEARCH_TYPES:
        return [build_es_schema_object(table, table_key, side, auto_create_target) for table in tables]
    if ds_type in DYNAMODB_TYPES:
        return [build_table_object(table.get(table_key), auto_create_target) for table in tables]
    if level == "NONE":
        return []

    grouped = []
    by_db = {}
    for table in tables:
        db_name = table.get(db_key)
        schema_name = table.get(schema_key)
        table_name = table.get(table_key)
        if not table_name:
            raise ValueError(side + " table is empty")

        if level == "DB_SCHEMA":
            db_obj = by_db.get(db_name)
            if db_obj is None:
                db_obj = {"db": db_name, "dbPattern": ""}
                if ds_type in ORACLE_TYPES:
                    db_obj["tableSpaces"] = []
                else:
                    db_obj["schemas"] = []
                by_db[db_name] = db_obj
                grouped.append(db_obj)

            schema_list_name = "tableSpaces" if ds_type in ORACLE_TYPES else "schemas"
            schema_name_key = "tableSpace" if ds_type in ORACLE_TYPES else "schema"
            schema_obj = None
            for item in db_obj[schema_list_name]:
                if item.get(schema_name_key) == schema_name:
                    schema_obj = item
                    break
            if schema_obj is None:
                schema_obj = {
                    schema_name_key: schema_name,
                    schema_name_key + "Pattern": "",
                    "tables": [],
                    "targetAutoCreate": bool(auto_create_target),
                }
                db_obj[schema_list_name].append(schema_obj)
            schema_obj["tables"].append(
                build_table_object(
                    table_name,
                    auto_create_target,
                    table.get(side + "Columns"),
                    table.get(side + "SpecifiedPks", [] if side == "source" else None),
                )
            )
        else:
            root_name = schema_name or db_name
            db_obj = by_db.get(root_name)
            if db_obj is None:
                db_obj = {"db": root_name, "dbPattern": "", "tables": []}
                by_db[root_name] = db_obj
                grouped.append(db_obj)
            db_obj["tables"].append(
                build_table_object(
                    table_name,
                    auto_create_target,
                    table.get(side + "Columns"),
                    table.get(side + "SpecifiedPks", [] if side == "source" else None),
                )
            )
    return grouped


def build_target_schema_json(src_type, dst_type, dst_level, tables, auto_create_target=False):
    if dst_type in MQ_TYPES | REDIS_TYPES | SEARCH_TYPES:
        return build_schema_json(dst_type, "NONE", tables, "target", auto_create_target)
    if dst_type in DYNAMODB_TYPES:
        return build_schema_json(dst_type, "NONE", tables, "target", auto_create_target)
    if src_type in MQ_TYPES:
        return build_schema_json(dst_type, dst_level, tables, "target", auto_create_target)
    if dst_type in DRDS_TYPES | TDSQL_MYSQL_TYPES | PARTITION_EXPR_TYPES | GREPTIME_TYPES | HIVE_TYPES:
        return build_schema_json(dst_type, dst_level, tables, "target", auto_create_target)
    return None


def endpoint_obj(table, side, level, ds_type=None):
    db = table.get(side + "Db")
    schema = table.get(side + "Schema")
    table_name = table.get(side + "Table")
    if ds_type in NO_DB_TYPES:
        return compare_obj(table_name)
    if level == "DB_SCHEMA":
        return compare_obj(table_name, compare_obj(schema, compare_obj(db)))
    return compare_obj(table_name, compare_obj(schema or db))


def schema_obj(table, side, level):
    db = table.get(side + "Db")
    schema = table.get(side + "Schema")
    if level == "DB_SCHEMA":
        return compare_obj(schema, compare_obj(db))
    return compare_obj(schema or db)


def db_obj(table, side):
    return compare_obj(table.get(side + "Db") or table.get(side + "Schema"))


def default_table_method(src_type, dst_type):
    if src_type in MQ_TYPES:
        if dst_type in KAFKA_TYPES | ROCKETMQ_TYPES | PULSAR_TYPES:
            return "TOPIC_TOPIC"
        if dst_type in NO_DB_TYPES:
            return "TOPIC_INDEX"
        return "TOPIC_TABLE"
    if dst_type in MQ_TYPES | RAG_API_TYPES:
        return "TABLE_TOPIC"
    if dst_type in REDIS_TYPES:
        return "TABLE_KEYPREFIX"
    if dst_type in SEARCH_TYPES:
        return "TABLE_INDEX"
    return "TABLE_TABLE"


def schema_mapping_method(src_type, dst_type):
    if src_type in HAS_SCHEMA_TYPES:
        if dst_type in HAS_SCHEMA_TYPES:
            return "SCHEMA_SCHEMA"
        return "SCHEMA_DB"
    if dst_type in HAS_SCHEMA_TYPES:
        return "DB_SCHEMA"
    return "DB_DB"


def add_db_mappings(mapping, tables):
    for table in tables:
        add_mapping(mapping, db_obj(table, "source"), db_obj(table, "target"))


def add_schema_mappings(mapping, tables, src_level, dst_level):
    for table in tables:
        add_mapping(mapping, schema_obj(table, "source", src_level), schema_obj(table, "target", dst_level))


def add_table_mappings(mapping, tables, src_level, dst_level, src_type, dst_type):
    for table in tables:
        add_mapping(mapping, endpoint_obj(table, "source", src_level, src_type), endpoint_obj(table, "target", dst_level, dst_type))


def add_any_db_mapping(mapping, tables):
    for table in tables:
        target_db = table.get("targetDb") or table.get("targetSchema")
        if target_db:
            add_mapping(mapping, compare_obj("ANY_DB"), compare_obj(target_db))
            return


def add_any_schema_mapping(mapping, tables):
    for table in tables:
        target_schema = table.get("targetSchema")
        target_db = table.get("targetDb")
        if target_schema and target_db:
            add_mapping(mapping, compare_obj("ANY_SCHEMA"), compare_obj(target_schema, compare_obj(target_db)))
            return
        if target_schema or target_db:
            add_mapping(mapping, compare_obj("ANY_SCHEMA"), compare_obj(target_schema or target_db))
            return


def build_column_mapping(src_type, dst_type, src_level, dst_level, column_rule, tables):
    column_mapping = level_mapping("COLUMN_COLUMN", column_rule)
    if src_type in NO_COLUMN_TYPES:
        return column_mapping
    for table in tables:
        for src_col, dst_col in table.get("columnMaps") or []:
            src_table_obj = endpoint_obj(table, "source", src_level, src_type)
            dst_table_obj = endpoint_obj(table, "target", dst_level, dst_type)
            add_mapping(column_mapping, compare_obj(src_col, src_table_obj), compare_obj(dst_col, dst_table_obj))
    return column_mapping


def build_mapping_def(src_type, dst_type, src_level, dst_level, schema_rule, table_rule, column_rule, tables, args):
    schema_common_rule = "MIRROR"
    mappings = []

    def table_mapping(method, rule=table_rule, from_type=src_type, to_type=dst_type):
        mapping = level_mapping(args.table_mapping_method or method, rule)
        add_table_mappings(mapping, tables, src_level, dst_level, from_type, to_type)
        return mapping

    def column_mapping():
        return build_column_mapping(src_type, dst_type, src_level, dst_level, column_rule, tables)

    db_mapping = level_mapping("DB_DB", schema_common_rule)
    add_db_mappings(db_mapping, tables)

    schema_method = schema_mapping_method(src_type, dst_type)
    schema_mapping = level_mapping(schema_method, schema_common_rule)
    if schema_method != "DB_DB":
        add_schema_mappings(schema_mapping, tables, src_level, dst_level)

    if src_type in MQ_TYPES:
        if dst_type in HAS_SCHEMA_TYPES:
            any_schema = level_mapping("ANY_SCHEMA", "MIRROR")
            add_any_schema_mapping(any_schema, tables)
            mappings.append(any_schema)
            mappings.append(table_mapping("TOPIC_TABLE"))
        elif dst_type not in NO_DB_TYPES:
            any_db = level_mapping("ANY_DB", "MIRROR")
            add_any_db_mapping(any_db, tables)
            mappings.append(any_db)
            mappings.append(table_mapping("TABLE_TABLE" if src_type in TUNNEL_TYPES else "TOPIC_TABLE"))
        elif dst_type in KAFKA_TYPES | ROCKETMQ_TYPES | PULSAR_TYPES:
            mappings.append(table_mapping("TOPIC_TOPIC"))
        else:
            mappings.append(table_mapping("TOPIC_INDEX"))
    elif src_type in HAS_SCHEMA_TYPES:
        if dst_type in HAS_SCHEMA_TYPES:
            mappings.extend([db_mapping, schema_mapping, table_mapping("TABLE_TABLE"), column_mapping()])
        elif src_type in ORACLE_TYPES and dst_type in KUDU_TYPES:
            mappings.extend([table_mapping("TABLE_TABLE", from_type=src_type, to_type=dst_type), column_mapping()])
        elif dst_type in MQ_TYPES | RAG_API_TYPES:
            mappings.extend([table_mapping("TABLE_TOPIC"), column_mapping()])
        elif dst_type in SEARCH_TYPES:
            mappings.extend([table_mapping("TABLE_INDEX"), column_mapping()])
        else:
            mappings.extend([schema_mapping, table_mapping("TABLE_TABLE"), column_mapping()])
    elif dst_type in HAS_SCHEMA_TYPES:
        mappings.extend([schema_mapping, table_mapping("TABLE_TABLE"), column_mapping()])
    elif dst_type in MQ_TYPES | RAG_API_TYPES:
        mappings.extend([table_mapping("TABLE_TOPIC"), column_mapping()])
    elif dst_type in REDIS_TYPES:
        mappings.extend([table_mapping("TABLE_KEYPREFIX"), column_mapping()])
    elif dst_type in SEARCH_TYPES:
        mappings.extend([table_mapping("TABLE_TABLE" if src_type in SEARCH_TYPES else "TABLE_INDEX"), column_mapping()])
    elif src_type in DYNAMODB_TYPES:
        any_db = level_mapping("ANY_DB", "MIRROR")
        add_any_db_mapping(any_db, tables)
        mappings.extend([any_db, table_mapping("TABLE_TABLE"), column_mapping()])
    elif dst_type in DYNAMODB_TYPES:
        mappings.extend([table_mapping("TABLE_TABLE"), column_mapping()])
    else:
        mappings.extend([db_mapping, table_mapping(default_table_method(src_type, dst_type)), column_mapping()])
    return mappings


def source_schema_table_objects(source_schema):
    for db_obj in source_schema or []:
        for table in db_obj.get("tables") or []:
            yield table
        for schema_obj in db_obj.get("schemas") or []:
            for table in schema_obj.get("tables") or []:
                yield table
        for schema_obj in db_obj.get("tableSpaces") or []:
            for table in schema_obj.get("tables") or []:
                yield table


def validate_source_schema_columns(source_type, source_schema):
    if source_type in NO_COLUMN_TYPES:
        return
    missing = []
    for table in source_schema_table_objects(source_schema):
        table_name = table.get("table")
        if table_name and not table.get("columns"):
            missing.append(table_name)
    if missing:
        raise ApiError(
            "sourceSchema columns are empty for RDB tables: "
            + ",".join(missing)
            + ". Frontend create flow fills selected columns; empty columns can make full sync write default values."
        )


def resolve_job_mode(args):
    mode = (args.mode or "").lower()
    job_type = args.job_type
    initial_sync = False
    short_term_sync = False
    check_once = False
    struct_migration = bool(args.struct_migration)
    if mode in ("migration", "full"):
        job_type = job_type or "MIGRATION"
        struct_migration = True if args.struct_migration is None else struct_migration
    elif mode in ("full-sync", "sync"):
        job_type = job_type or "SYNC"
        initial_sync = True
        struct_migration = True if args.struct_migration is None else struct_migration
    elif mode in ("increment", "incremental"):
        job_type = job_type or "SYNC"
    elif mode == "check":
        job_type = job_type or "CHECK"
        check_once = True
    elif mode == "struct":
        job_type = job_type or "STRUCT_MIGRATION"
        struct_migration = True
    else:
        raise ValueError("unsupported --mode: " + str(args.mode))
    return job_type, initial_sync, short_term_sync, check_once, struct_migration


def verify_job_support(client, payload, datasources):
    source_id = parse_int(payload.get("sourceDataSourceId"), "sourceDataSourceId")
    target_id = parse_int(payload.get("targetDataSourceId"), "targetDataSourceId")
    source = datasources.get(source_id) or query_datasource(client, source_id)
    target = datasources.get(target_id) or query_datasource(client, target_id)
    source_type = data_source_type(source)
    target_type = data_source_type(target)
    job_type = payload.get("jobType")
    route = f"{source_type} -> {target_type} ({job_type})"
    query = {
        "sourceType": source_type,
        "targetType": target_type,
        "cgTableType": source.get("cgTableType") or "BASE_TABLE",
    }
    response = client.post_json(TRANSFORM_JOB_TYPE_PATH, query)
    support = success_data(client, response, f"verify Console task support for {route}")
    if not isinstance(support, dict) or support.get("source") != source_type or support.get("target") != target_type:
        raise ApiError(f"Console returned no matching task support for {route}")

    options = support.get("optionType")
    if not isinstance(options, dict) or not isinstance(job_type, str) or not isinstance(options.get(job_type), dict):
        raise ApiError(f"Console does not offer this task type for {route}")

    modes = options[job_type]
    if job_type == "SYNC" and modes.get("Incremental") not in (True, "true"):
        raise ApiError(f"Console does not support incremental sync for {route}")
    requests_full = job_type == "MIGRATION" or (job_type == "SYNC" and payload.get("initialSync"))
    if requests_full and modes.get("FullAmount") not in (True, "true"):
        raise ApiError(f"Console does not support a full load for {route}")


def build_datajob_payload(args, client, *, target_names=None):
    source_id = parse_int(args.source_ds_id, "sourceDataSourceId")
    target_id = parse_int(args.target_ds_id, "targetDataSourceId")
    source_ds = query_datasource(client, source_id)
    target_ds = query_datasource(client, target_id)
    source_type = normalize_ds_type(args.source_type) if args.source_type else data_source_type(source_ds)
    target_type = normalize_ds_type(args.target_type) if args.target_type else data_source_type(target_ds)

    cluster_id = resolve_cluster_id(args, client)
    source_host_type = host_type_value(args.source_host_type or source_ds.get("hostType"))
    target_host_type = host_type_value(args.target_host_type or target_ds.get("hostType"))
    target_deploy_type = target_ds.get("deployType")
    schema_rule = fetch_schema_mapping_rule(client, source_type, target_type, target_deploy_type)
    source_level = schema_level(source_type, schema_rule, "source")
    target_level = schema_level(target_type, schema_rule, "target")

    table_rules = fetch_table_mapping_rules(client, cluster_id, source_type, target_type, target_id, target_host_type, args.table_select_mode)
    column_rules = fetch_column_mapping_rules(client, source_type, target_type)
    table_rule = args.table_rule or choose_default_rule(table_rules, schema_rule.get("mappingRule") or "MIRROR")
    column_rule = args.column_rule or choose_default_rule(column_rules, "MIRROR")

    source_schema_json = read_json_arg(args.source_schema_json)
    target_schema_json = read_json_arg(args.target_schema_json)
    mapping_json = read_json_arg(args.mapping_json)
    tables = []
    if source_schema_json is None or mapping_json is None:
        tables = parse_table_args(args, source_level, target_level, schema_rule, table_rule, target_names)
        parse_column_maps(args, tables)
    if source_schema_json is None:
        enrich_source_columns(client, source_id, cluster_id, source_type, source_level, source_host_type, tables, args.auto_create_target)
    if source_schema_json is None:
        source_schema_json = build_schema_json(source_type, source_level, tables, "source", args.auto_create_target)
    validate_source_schema_columns(source_type, source_schema_json)
    if target_schema_json is None:
        target_schema_json = build_target_schema_json(source_type, target_type, target_level, tables, args.auto_create_target)
    if mapping_json is None:
        mapping_json = build_mapping_def(source_type, target_type, source_level, target_level, schema_rule, table_rule, column_rule, tables, args)

    job_type, initial_sync, short_term_sync, check_once, struct_migration = resolve_job_mode(args)
    spec_id = resolve_spec_id(args, client, job_type, initial_sync, short_term_sync)
    processor_config = read_json_arg(args.processor_config_json, [])
    payload = {
        "jobType": job_type,
        "dataJobDesc": args.desc or "",
        "structMigration": struct_migration,
        "initialSync": initial_sync,
        "shortTermSync": short_term_sync,
        "checkOnce": check_once,
        "checkPeriod": False,
        "fullPeriod": False,
        "cleanTargetBeforeFull": bool(args.clean_target_before_full),
        "autoStart": bool(args.auto_start),
        "clusterId": cluster_id,
        "dataJobLevel": args.level,
        "sourceSchema": json.dumps(source_schema_json, ensure_ascii=False, separators=(",", ":")),
        "targetSchema": json.dumps(target_schema_json, ensure_ascii=False, separators=(",", ":")) if target_schema_json is not None else None,
        "mappingDef": json.dumps(mapping_json, ensure_ascii=False, separators=(",", ":")),
        "sourceDataSourceId": source_id,
        "targetDataSourceId": target_id,
        "sourceHostType": source_host_type,
        "targetHostType": target_host_type,
        "specId": spec_id,
        "srcDsCharset": args.source_charset or query_default_charset(client, source_type),
        "tarDsCharset": args.target_charset or query_default_charset(client, target_type),
        "filterDDL": bool(args.filter_ddl),
        "processorConfigList": processor_config,
        "keyConflictStrategy": args.key_conflict_strategy,
    }
    if args.job_name:
        payload["specifiedJobName"] = True
        payload["specifiedJobNameVal"] = args.job_name
    if args.short_term_num is not None:
        payload["shortTermNum"] = args.short_term_num
    dynamic_defaults = default_extra_json(fetch_job_extra_configs(client, source_type, target_type))
    deep_merge(payload, dynamic_defaults)
    deep_merge(payload, datasource_task_extra_json(client, source_id, source_type))
    deep_merge(payload, datasource_task_extra_json(client, target_id, target_type))
    extra = read_json_arg(args.extra_json, {})
    deep_merge(payload, extra)
    verify_job_support(client, payload, {source_id: source_ds, target_id: target_ds})
    return payload


def failed_prechecks(items):
    result = []
    for item in items or []:
        if item.get("success") is False:
            result.append(item)
    return result


def precheck_final(client, payload):
    response = client.post_json(PRECHECK_FINAL_PATH, payload)
    return success_data(client, response, "final precheck") or []


def precheck(client, stage, payload=None):
    if stage == "first":
        response = client.post_json(PRECHECK_FIRST_PATH, {})
        return success_data(client, response, "first precheck")
    if stage == "step-two":
        response = client.post_json(PRECHECK_STEP_TWO_PATH, payload)
        return success_data(client, response, "step two precheck") or []
    if stage == "step-three":
        response = client.post_json(PRECHECK_STEP_THREE_PATH, payload)
        return success_data(client, response, "step three precheck")
    if stage == "obj-necessary":
        response = client.post_json(PRECHECK_OBJ_NECESSARY_PATH, payload)
        return success_data(client, response, "object necessary precheck") or []
    if stage == "final":
        return precheck_final(client, payload)
    raise ValueError("unsupported precheck stage: " + str(stage))


def precheck_title(item):
    title = item.get("title")
    if title:
        return str(title)
    return json.dumps(item, ensure_ascii=False, separators=(",", ":"))


def create_datajob_cmd(args, client):
    if args.precheck_only and args.skip_precheck:
        raise ValueError("--precheck-only cannot be combined with --skip-precheck")
    payload = build_datajob_payload(args, client)
    if args.dry_run:
        print("\nDry run dataJobData:")
        print_json(mask_payload(payload))
        return 0

    if not args.skip_precheck:
        items = precheck(client, args.precheck_stage, payload)
        if not isinstance(items, list):
            items = []
        failures = failed_prechecks(items)
        print(args.precheck_stage + " precheck finished, items=" + str(len(items)) + ", failed=" + str(len(failures)))
        if failures:
            for item in failures[:10]:
                print("  - " + precheck_title(item))
            if not args.ignore_precheck_fail:
                raise ApiError("final precheck failed; use --ignore-precheck-fail to create anyway")
        if args.precheck_only:
            print_json(items)
            return 0

    response = client.post_multipart(CREATE_JOB_PATH, {"dataJobData": json_part(payload)})
    data_job_id = success_data(client, response, "create data job")
    print("Data job created, id=" + str(data_job_id))
    if args.start_after_create:
        wait_job_creation(client, data_job_id, args.start_timeout_seconds)
        start_job(client, data_job_id)
    return 0


def query_job(client, job_id):
    response = client.post_json(QUERY_JOB_PATH, {"jobId": parse_int(job_id, "jobId")})
    return success_data(client, response, "query data job")


def wait_job_creation(client, job_id, timeout_seconds, summarize=None):
    deadline = time.time() + max(int(timeout_seconds or 0), 1)
    last = None
    while time.time() < deadline:
        job = query_job(client, job_id)
        last = summarize(job) if summarize else {key: job.get(key) for key in ("dataJobId", "lifeCycleState", "consoleJobId", "consoleTaskState")}
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


def job_source_ds(data):
    return data.get("sourceDsVO") or {}


def job_target_ds(data):
    return data.get("targetDsVO") or {}


def query_job_schema(client, job_id, src_type=None, dst_type=None):
    data = query_job(client, job_id)
    payload = {"jobId": parse_int(job_id, "jobId")}
    payload["srcDsType"] = src_type or data_source_type(job_source_ds(data))
    payload["dstDsType"] = dst_type or data_source_type(job_target_ds(data))
    response = client.post_json(QUERY_JOB_SCHEMA_PATH, payload)
    return success_data(client, response, "query data job schema")


def list_jobs_by_page(client, payload):
    response = client.post_json(LIST_JOBS_BY_PAGE_PATH, payload)
    return success_data(client, response, "list data jobs")


def job_name(data):
    if not data:
        return ""
    return data.get("dataJobName") or ""


def parse_id_list(values, name):
    result = []
    for value in values or []:
        for item in str(value).split(","):
            item = item.strip()
            if item:
                result.append(parse_int(item, name))
    if not result:
        raise ValueError(name + " is required")
    return result


def job_action_payload(client, job_id, data_job_name=None):
    parsed_job_id = parse_int(job_id, "jobId")
    name = data_job_name
    if not name:
        name = job_name(query_job(client, parsed_job_id))
    if not name:
        raise ValueError("dataJobName not found for jobId " + str(parsed_job_id))
    return {"jobId": parsed_job_id, "dataJobName": name}


JOB_ACTIONS = {
    "start": (START_JOB_PATH, START_BATCH_PATH, "started", "start data job"),
    "stop": (STOP_JOB_PATH, STOP_BATCH_PATH, "stopped", "stop data job"),
    "restart": (RESTART_JOB_PATH, RESTART_BATCH_PATH, "restarted", "restart data job"),
    "replay": (REPLAY_JOB_PATH, None, "replayed", "replay data job"),
    "active-fsm": (ACTIVE_FSM_PATH, ACTIVE_FSM_BATCH_PATH, "continued after structure migration", "active data job fsm"),
}
DELETE_BUSY_TASK_STATUSES = {"WAIT_START", "RUNNING"}
DELETE_READY_WAIT_SECONDS = 30


def job_action_result(client, action, job_id, data_job_name=None):
    if action not in JOB_ACTIONS:
        raise ValueError("unsupported job action: " + str(action))
    path, _batch_path, _done, label = JOB_ACTIONS[action]
    payload = job_action_payload(client, job_id, data_job_name)
    response = client.post_json(path, payload)
    success_data(client, response, label)
    return {"path": path, "payload": payload}


def operate_job(client, action, job_id, data_job_name=None, dry_run=False):
    if action not in JOB_ACTIONS:
        raise ValueError("unsupported job action: " + str(action))
    path, _batch_path, done, label = JOB_ACTIONS[action]
    payload = job_action_payload(client, job_id, data_job_name)
    if dry_run:
        print_json({"path": path, "payload": payload})
        return None
    job_action_result(client, action, job_id, data_job_name)
    print("Data job " + done + ", id=" + str(payload["jobId"]))
    return None


def operate_jobs(client, action, job_ids, dry_run=False):
    if action not in JOB_ACTIONS:
        raise ValueError("unsupported job action: " + str(action))
    single_path, batch_path, done, label = JOB_ACTIONS[action]
    ids = parse_id_list(job_ids, "jobId")
    if len(ids) == 1 or not batch_path:
        for job_id in ids:
            operate_job(client, action, job_id, dry_run=dry_run)
        return None

    payload = [job_action_payload(client, job_id) for job_id in ids]
    if dry_run:
        print_json({"path": batch_path, "payload": payload})
        return None
    response = client.post_json(batch_path, payload)
    success_data(client, response, label + " batch")
    print("Data jobs " + done + ", ids=" + ",".join(str(item) for item in ids))
    return None


def start_job(client, job_id):
    return job_action_result(client, "start", job_id)


def active_fsm_job(client, job_id):
    return job_action_result(client, "active-fsm", job_id)


def stop_job(client, job_id):
    return job_action_result(client, "stop", job_id)


def fsm_id_from_job(job):
    value = job.get("fsmId")
    if not value:
        return None
    return parse_int(value, "fsmId")


def list_fsm(client, payload):
    response = client.post_json(FSM_LIST_PATH, payload or {})
    return success_data(client, response, "list fsm")


def find_fsm_by_job(client, job_id, data_job_name=None):
    parsed_job_id = parse_int(job_id, "jobId")
    job = query_job(client, parsed_job_id)
    fsm_id = fsm_id_from_job(job)
    if fsm_id:
        return {"fsmId": fsm_id, "job": job, "source": "query-job"}

    rows = list_fsm(client, {"dataJobId": parsed_job_id})
    if not isinstance(rows, list):
        raise ApiError("fsm list for data job " + str(parsed_job_id) + " was not a DataTaskFSMVO list")
    for row in rows:
        if row.get("dataJobId") == parsed_job_id:
            return {"fsmId": parse_int(row.get("id"), "fsmId"), "job": job, "fsm": row, "source": "fsm-list"}
    raise ApiError("fsm id not found for data job " + str(parsed_job_id))


def fsm_action_result(client, action, fsm_id=None, job_id=None, data_job_name=None):
    payload = {}
    if fsm_id:
        payload["fsmId"] = parse_int(fsm_id, "fsmId")
    if not payload.get("fsmId"):
        found = find_fsm_by_job(client, job_id, data_job_name)
        payload["fsmId"] = found["fsmId"]
    if action == "activate":
        path = FSM_ACTIVATE_PATH
        if job_id:
            payload["dataJobId"] = parse_int(job_id, "dataJobId")
    elif action == "inactivate":
        path = FSM_INACTIVATE_PATH
    else:
        raise ValueError("unsupported fsm action: " + str(action))
    response = client.post_json(path, payload)
    success_data(client, response, action + " fsm")
    return {"path": path, "payload": payload}


def inactivate_fsm_for_job(client, job_id, data_job_name=None):
    return fsm_action_result(client, "inactivate", job_id=job_id, data_job_name=data_job_name)


def delete_brief(job):
    return {
        "jobId": job.get("dataJobId"),
        "name": job_name(job),
        "currTaskStatus": job.get("currTaskStatus"),
        "dataTaskState": job.get("dataTaskState"),
        "fsmActive": job.get("fsmActive"),
        "lifeCycleState": job.get("lifeCycleState"),
        "tasks": [
            {
                "type": task.get("dataTaskType"),
                "status": task.get("dataTaskStatus"),
            }
            for task in job.get("dataTasks") or []
        ],
    }


def job_busy_for_delete(job):
    if job.get("currTaskStatus") in DELETE_BUSY_TASK_STATUSES:
        return True
    return any(task.get("dataTaskStatus") in DELETE_BUSY_TASK_STATUSES for task in job.get("dataTasks") or [])


def wait_job_not_busy_for_delete(client, job_id, timeout_seconds=DELETE_READY_WAIT_SECONDS):
    deadline = time.time() + max(int(timeout_seconds or 0), 1)
    last = None
    while time.time() < deadline:
        job = query_job(client, job_id)
        last = delete_brief(job)
        if not job_busy_for_delete(job):
            return {"ready": True, "last": last}
        time.sleep(3)
    return {"ready": False, "last": last}


def delete_job_with_cleanup(client, job_id, data_job_name=None, stop_first=False, inactivate_fsm=False, delete_children=False, dry_run=False):
    parsed_job_id = parse_int(job_id, "jobId")
    actions = []
    if dry_run:
        return {
            "jobId": parsed_job_id,
            "jobName": data_job_name,
            "deleteChildren": delete_children,
            "stopFirst": stop_first,
            "inactivateFsm": inactivate_fsm,
            "deletePath": DELETE_JOB_PATH,
            "note": "dry-run does not query child jobs or resolve fsm id",
            "dryRun": True,
        }
    job = query_job(client, parsed_job_id)
    if delete_children:
        for child in job.get("childJobs") or []:
            child_id = child.get("dataJobId")
            if not child_id:
                continue
            actions.append(
                delete_job_with_cleanup(
                    client,
                    child_id,
                    data_job_name=job_name(child),
                    stop_first=stop_first,
                    inactivate_fsm=inactivate_fsm,
                    delete_children=True,
                    dry_run=dry_run,
                )
            )
    name = data_job_name or job_name(job)
    if stop_first:
        try:
            actions.append({"action": "stop", "result": stop_job(client, parsed_job_id)})
        except Exception as e:
            actions.append({"action": "stop", "ignored": True, "error": str(e)})
    if inactivate_fsm:
        try:
            actions.append({"action": "inactivate-fsm", "result": inactivate_fsm_for_job(client, parsed_job_id, name)})
        except Exception as e:
            actions.append({"action": "inactivate-fsm", "ignored": True, "error": str(e)})
    if stop_first or inactivate_fsm:
        try:
            actions.append({"action": "wait-delete-ready", "result": wait_job_not_busy_for_delete(client, parsed_job_id)})
        except Exception as e:
            actions.append({"action": "wait-delete-ready", "ignored": True, "error": str(e)})
    response = client.post_json(DELETE_JOB_PATH, {"jobId": parsed_job_id})
    success_data(client, response, "delete data job")
    return {"jobId": parsed_job_id, "jobName": name, "deleted": True, "actions": actions}


def delete_datajob_cmd(args, client):
    result = delete_job_with_cleanup(
        client,
        args.job_id,
        data_job_name=getattr(args, "job_name", None),
        stop_first=getattr(args, "stop_first", False),
        inactivate_fsm=getattr(args, "inactivate_fsm", False),
        delete_children=getattr(args, "delete_children", False),
        dry_run=getattr(args, "dry_run", False),
    )
    print_json(result)
    return 0


def query_datajob_cmd(args, client):
    print_json(query_job(client, args.job_id))
    return 0


def query_datajob_schema_cmd(args, client):
    src_type = normalize_ds_type(args.source_type) if args.source_type else None
    dst_type = normalize_ds_type(args.target_type) if args.target_type else None
    print_json(query_job_schema(client, args.job_id, src_type, dst_type))
    return 0


def list_datajobs_cmd(args, client):
    payload = {
        "pageNum": args.page_num,
        "pageSize": args.page_size,
        "orderAsc": bool(args.order_asc),
    }
    optional_fields = {
        "desc": args.desc,
        "dataJobType": args.job_type,
        "dataJobName": args.job_name,
        "dataJobId": args.job_id,
        "sourceInstanceId": args.source_ds_id,
        "targetInstanceId": args.target_ds_id,
        "workerId": args.worker_id,
        "workerIp": args.worker_ip,
        "dataTaskStatus": args.task_status,
        "orderType": args.order_type,
        "transferObjName": args.transfer_obj_name,
    }
    for key, value in optional_fields.items():
        if value not in (None, ""):
            payload[key] = value
    extra = read_json_arg(args.payload_json, {})
    deep_merge(payload, extra)
    print_json(list_jobs_by_page(client, payload))
    return 0


def list_simple_datajobs_cmd(args, client):
    response = client.post_json(LIST_JOBS_SIMPLE_PATH, {})
    print_json(success_data(client, response, "list simple data jobs"))
    return 0


def list_check_tasks_cmd(args, client):
    response = client.post_json(LIST_CHECK_TASKS_PATH, {})
    print_json(success_data(client, response, "list check tasks"))
    return 0


def get_followed_jobs_cmd(args, client):
    payload = {
        "pageNum": args.page_num,
        "pageSize": args.page_size,
    }
    extra = read_json_arg(args.payload_json, {})
    deep_merge(payload, extra)
    response = client.post_json(GET_FOLLOWED_JOB_PATH, payload)
    print_json(success_data(client, response, "get followed jobs"))
    return 0


def precheck_cmd(args, client):
    payload = read_json_arg(args.payload_json, {})
    print_json(precheck(client, args.stage, payload))
    return 0


def job_id_raw_cmd(args, client, path, action):
    payload = {"jobId": parse_int(args.job_id, "jobId")}
    return raw_payload_cmd(args, client, path, action, payload)


def can_add_revise_task_cmd(args, client):
    return job_id_raw_cmd(args, client, CAN_ADD_REVISE_TASK_PATH, "can add revise task")


def add_revise_task_cmd(args, client):
    return job_id_raw_cmd(args, client, ADD_REVISE_TASK_PATH, "add revise task")


def attach_incre_task_cmd(args, client):
    return job_id_raw_cmd(args, client, ATTACH_INCRE_TASK_PATH, "attach incremental task")


def detach_incre_task_cmd(args, client):
    return job_id_raw_cmd(args, client, DETACH_INCRE_TASK_PATH, "detach incremental task")


def add_check_child_job_cmd(args, client):
    payload = {
        "jobId": parse_int(args.job_id, "jobId"),
        "checkOnce": bool(args.check_once),
        "checkPeriod": bool(args.check_period),
        "checkPeriodCronExpr": args.check_period_cron_expr,
        "fullCheck": bool(args.full_check),
        "fullPeriod": False,
        "fullPeriodCronExpr": None,
    }
    optional_fields = {
        "checkOnce": False if args.no_check_once else None,
        "fullCheck": False if args.no_full_check else None,
    }
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value
    return raw_payload_cmd(args, client, ADD_CHECK_CHILD_JOB_PATH, "add check child job", payload)


def generate_migration_tip_cmd(args, client):
    payload = read_json_arg(args.payload_json, {})
    if args.job_id:
        payload["dataJobId"] = parse_int(args.job_id, "dataJobId")
    if args.source_type:
        payload["srcDsType"] = normalize_ds_type(args.source_type)
    if args.target_type:
        payload["dstDsType"] = normalize_ds_type(args.target_type)
    if args.source_ds_id:
        payload["srcDsId"] = parse_int(args.source_ds_id, "srcDsId")
    if args.target_ds_id:
        payload["dstDsId"] = parse_int(args.target_ds_id, "dstDsId")
    if args.dry_run:
        print_json({"path": GENERATE_MIGRATION_TIP_PATH, "payload": payload})
        return 0
    response = client.post_json(GENERATE_MIGRATION_TIP_PATH, payload)
    print_json(success_data(client, response, "generate migration tip"))
    return 0


def start_datajob_cmd(args, client):
    operate_job(client, "start", args.job_id, getattr(args, "job_name", None), getattr(args, "dry_run", False))
    return 0


def stop_datajob_cmd(args, client):
    operate_job(client, "stop", args.job_id, getattr(args, "job_name", None), getattr(args, "dry_run", False))
    return 0


def restart_datajob_cmd(args, client):
    operate_job(client, "restart", args.job_id, getattr(args, "job_name", None), getattr(args, "dry_run", False))
    return 0


def replay_datajob_cmd(args, client):
    operate_job(client, "replay", args.job_id, getattr(args, "job_name", None), getattr(args, "dry_run", False))
    return 0


def active_fsm_datajob_cmd(args, client):
    operate_job(client, "active-fsm", args.job_id, getattr(args, "job_name", None), getattr(args, "dry_run", False))
    return 0


def list_fsm_cmd(args, client):
    payload = read_json_arg(args.payload_json, {})
    if getattr(args, "job_id", None):
        if args.dry_run:
            payload.setdefault("dataJobId", parse_int(args.job_id, "dataJobId"))
        else:
            job = query_job(client, parse_int(args.job_id, "jobId"))
            name = job_name(job)
            if name:
                payload.setdefault("dataJobName", name)
    if getattr(args, "job_name", None):
        payload["dataJobName"] = args.job_name
    if getattr(args, "state", None):
        payload["dataTaskState"] = "" if args.state == "all" else args.state
    if args.dry_run:
        print_json({"path": FSM_LIST_PATH, "payload": payload})
        return 0
    print_json(list_fsm(client, payload))
    return 0


def query_fsm_cmd(args, client):
    payload = read_json_arg(args.payload_json, {})
    if args.fsm_id:
        payload["fsmId"] = parse_int(args.fsm_id, "fsmId")
    if args.job_id:
        payload["dataJobId"] = parse_int(args.job_id, "dataJobId")
        if "fsmId" not in payload and not args.dry_run:
            payload["fsmId"] = find_fsm_by_job(client, args.job_id, getattr(args, "job_name", None))["fsmId"]
    if "fsmId" not in payload and not args.dry_run:
        raise ValueError("--fsm-id or --job-id is required")
    if args.dry_run:
        print_json({"path": FSM_DETAIL_PATH, "payload": payload})
        return 0
    response = client.post_json(FSM_DETAIL_PATH, payload)
    print_json(success_data(client, response, "query fsm"))
    return 0


def activate_fsm_cmd(args, client):
    if args.dry_run:
        payload = {}
        if args.fsm_id:
            payload["fsmId"] = parse_int(args.fsm_id, "fsmId")
        if args.job_id:
            payload["dataJobId"] = parse_int(args.job_id, "dataJobId")
        print_json({"path": FSM_ACTIVATE_PATH, "payload": payload})
        return 0
    print_json(fsm_action_result(client, "activate", args.fsm_id, args.job_id, getattr(args, "job_name", None)))
    return 0


def inactivate_fsm_cmd(args, client):
    if args.dry_run:
        payload = {}
        if args.fsm_id:
            payload["fsmId"] = parse_int(args.fsm_id, "fsmId")
        print_json({"path": FSM_INACTIVATE_PATH, "payload": payload})
        return 0
    print_json(fsm_action_result(client, "inactivate", args.fsm_id, args.job_id, getattr(args, "job_name", None)))
    return 0


def operate_datajobs_cmd(args, client):
    operate_jobs(client, args.action, args.job_id, args.dry_run)
    return 0


def update_job_desc_cmd(args, client):
    payload = {"jobId": parse_int(args.job_id, "jobId"), "dataJobDesc": args.desc}
    if args.dry_run:
        print_json({"path": UPDATE_DESC_PATH, "payload": payload})
        return 0
    response = client.post_json(UPDATE_DESC_PATH, payload)
    success_data(client, response, "update data job desc")
    print("Data job desc updated, id=" + str(payload["jobId"]))
    return 0


def update_job_level_cmd(args, client):
    payload = {"jobId": parse_int(args.job_id, "jobId"), "jobLevel": args.level}
    if args.dry_run:
        print_json({"path": UPDATE_LEVEL_PATH, "payload": payload})
        return 0
    response = client.post_json(UPDATE_LEVEL_PATH, payload)
    success_data(client, response, "update data job level")
    print("Data job level updated, id=" + str(payload["jobId"]))
    return 0


def query_job_options_cmd(args, client):
    response = client.post_json(QUERY_JOB_OPTIONS_PATH, {"jobId": parse_int(args.job_id, "jobId")})
    print_json(success_data(client, response, "query data job options"))
    return 0


def update_job_options_cmd(args, client):
    options = read_json_arg(args.options_json, {})
    for item in args.set or []:
        if "=" not in item:
            raise ValueError("--set expects key=value, got: " + item)
        key, value = item.split("=", 1)
        options[key.strip()] = value
    if not options:
        raise ValueError("--options-json or --set is required")
    payload = {"jobId": parse_int(args.job_id, "jobId"), "options": options}
    if args.dry_run:
        print_json({"path": UPDATE_JOB_OPTIONS_PATH, "payload": payload})
        return 0
    response = client.post_json(UPDATE_JOB_OPTIONS_PATH, payload)
    success_data(client, response, "update data job options")
    print("Data job options updated, id=" + str(payload["jobId"]))
    return 0


def raw_payload_cmd(args, client, path, action, default_payload=None):
    payload = default_payload or {}
    extra = read_json_arg(args.payload_json, {})
    deep_merge(payload, extra)
    if args.dry_run:
        print_json({"path": path, "payload": payload})
        return 0
    response = client.post_json(path, payload)
    data = success_data(client, response, action)
    if data is not None:
        print_json(data)
    else:
        print(action + " succeeded")
    return 0


def update_transfer_object_cmd(args, client):
    path = UPDATE_TRANSFER_OBJECT_FOR_FULL_PATH if args.full else UPDATE_TRANSFER_OBJECT_PATH
    payload = {"dataJobId": parse_int(args.job_id, "dataJobId")}
    return raw_payload_cmd(args, client, path, "update transfer object", payload)


def json_string_arg(value, fallback=None):
    if value in (None, ""):
        return fallback
    parsed = read_json_arg(value)
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def partition_subscription(nodes, selected, parent=()):
    """Split saved objects while preserving the Console's per-engine schema and table options."""
    retained, removed = [], []
    for node in nodes:
        if node.get("inBlackList"):
            retained.append(node)
            continue
        if any(node.get(key) not in (None, "", False, "false") for key in
               ("pattern", "dbPattern", "schemaPattern", "tableSpacePattern", "topicPattern", "queuePattern")):
            raise ValueError("cannot infer a subscription edit containing a pattern; supply the full edit payload")
        child_key = next((key for key in ("schemas", "tableSpaces", "tables", "collections") if key in node), None)
        if child_key:
            name_key = {"schemas": "db", "tableSpaces": "db"}.get(child_key)
            if name_key is None:
                name_key = next((key for key in ("schema", "tableSpace", "db") if key in node), "db")
            name = node.get(name_key)
            nested = parent + (name,) if name else parent
            keep, drop = partition_subscription(node[child_key] or [], selected, nested)
            if keep or not drop:
                retained.append({**node, child_key: keep})
            if drop:
                removed.append({**node, child_key: drop})
            continue

        leaf = next((key for key in ("table", "collection", "topic", "queue", "indexName", "prefix", "keyPrefix") if node.get(key)), None)
        if leaf and selected(parent + (node[leaf],)):
            removed.append(node)
        else:
            retained.append(node)
    return retained, removed


def compare_path(encoded):
    item = json.loads(encoded)
    parts = []
    while item:
        if not isinstance(item, dict) or not isinstance(item.get("value"), str):
            raise ValueError("invalid object path in saved mapping: " + encoded)
        parts.append(item["value"])
        item = item.get("parent")
    return tuple(reversed(parts))


def removed_subscription(args, schema, src_level, dst_level, dst_type, overrides, target_case_sensitive):
    if schema.get("schemaWhiteListLevel") in {"INSTANCE", "DB", "SCHEMA"}:
        raise ValueError("--remove-table requires a table subscription; use the Console edit payload for database-wide subscriptions")
    requests = {}
    explicit_targets = {}
    for entry in args.remove_table:
        source, sep, target = entry.partition("=")
        src = parse_table_path(source.strip(), src_level, args.source_db, args.source_schema)
        if src_level == "DB_SCHEMA":
            key = (src["db"], src["schema"], src["table"])
        elif src_level == "NONE":
            key = (src["table"],)
        else:
            key = (src["schema"] or src["db"], src["table"])
        requests.setdefault(key, [])
        if sep or args.target_db or args.target_schema or args.target_table:
            dst = parse_table_path(target.strip() if sep else args.target_table or src["table"], dst_level, args.target_db, args.target_schema)
            explicit_targets[key] = tuple(part for part in (dst["db"], dst["schema"], dst["table"]) if part)

    all_sources = set()

    def select_source(path):
        all_sources.add(path)
        matched = False
        for key, found in requests.items():
            if len(key) == len(path) and all(want is None or want == actual for want, actual in zip(key, path)):
                found.append(path)
                matched = True
        return matched

    source = json.loads(schema.get("sourceSchema") or "[]")
    retained, removed = partition_subscription(source, select_source)
    for key, found in requests.items():
        if len(found) != 1:
            raise ValueError(f"--remove-table {key} matches {len(found)} subscribed objects; specify its database and schema")
    removed_paths = {found[0] for found in requests.values()}

    def source_for_mapping(path):
        if path in all_sources or not path:
            return path
        # Some frontend table/topic keys omit the source schema or all parents.
        candidates = [p for p in all_sources if p[-1] == path[-1] and (len(path) == 1 or p[:-2] == path[:-1])]
        if len(candidates) == 1:
            return candidates[0]
        if removed_paths.intersection(candidates):
            raise ValueError(f"ambiguous saved source mapping {path}; supply the full edit payload")
        return path

    retained_paths = all_sources - removed_paths
    retired_parents = {p[:i] for p in removed_paths for i in range(1, len(p))}
    retired_parents.difference_update(p[:i] for p in retained_paths for i in range(1, len(p)))
    target_hints = {requests[key][0]: value for key, value in explicit_targets.items()}
    result = {"srcSchemaWithoutAdd": compare_obj_json(retained), "reduceConfig": compare_obj_json(removed)}

    target = json.loads(schema.get("targetSchema") or "[]")
    oracle_cleanup = dst_type in {"Oracle", "ObForOracle"} and "targetReduceConfig" not in overrides
    needs_target = (target and "dstSchemaWithoutAdd" not in overrides) or oracle_cleanup
    if not needs_target and "mappingConfigWithoutAdd" in overrides:
        return result
    mappings = json.loads(schema.get("mappingConfig") or "[]")
    parent_mappings = {}
    generated_parents = False
    table_targets = {}
    table_rules = {}
    db_topic = False
    common_rule = "MIRROR"
    for layer in mappings:
        method = layer["method"]
        table_layer = method.startswith(("TABLE_", "TOPIC_"))
        column_layer = method == "COLUMN_COLUMN"
        if method == "REGEX_TABLE_TABLE":
            raise ValueError("cannot infer a subscription edit for REGEX_TABLE_TABLE; supply the full edit payload")
        if method == "DB_TOPIC":
            db_topic = True
        if table_layer or method == "DB_TOPIC":
            common_rule = layer.get("commonGenRule") or "MIRROR"
        elif not column_layer:
            if layer.get("serializeAutoGenRules") or layer.get("commonGenRule") not in (None, "MIRROR", "MIRROR_IGNORE_CASE"):
                generated_parents = True
        for field in ("serializeMapping", "serializeAutoGenRules"):
            entries = layer.get(field) or {}
            for encoded, value in list(entries.items()):
                path = compare_path(encoded)
                if table_layer:
                    path = source_for_mapping(path)
                elif column_layer:
                    path = source_for_mapping(path[:-1]) + path[-1:]
                if (table_layer or method == "DB_TOPIC") and field == "serializeMapping":
                    dest = compare_path(value)
                    if path in table_targets and table_targets[path] != dest:
                        raise ValueError(f"conflicting saved destination mappings for {path}; supply the full edit payload")
                    table_targets[path] = dest
                elif table_layer or method == "DB_TOPIC":
                    table_rules[path] = value
                elif field == "serializeMapping" and method in ("DB_DB", "SCHEMA_DB", "DB_SCHEMA", "SCHEMA_SCHEMA", "ANY_DB", "ANY_SCHEMA"):
                    parent_mappings[path] = compare_path(value)
                if table_layer:
                    remove_entry = path in removed_paths
                elif column_layer:
                    remove_entry = path[:-1] in removed_paths
                else:
                    remove_entry = path in retired_parents
                if remove_entry:
                    del entries[encoded]
    result["mappingConfigWithoutAdd"] = compare_obj_json(mappings)

    if not needs_target:
        return result

    def destination(path):
        key = path[:1] if db_topic else path
        if key in table_targets:
            return table_targets[key]
        if path in target_hints:
            return target_hints[path]
        rule = table_rules.get(key, common_rule)
        if rule not in ("MIRROR", "MIRROR_IGNORE_CASE", "EXPRESSION_MAPPING", "TO_UPPER_CASE", "TO_LOWER_CASE"):
            raise ValueError(f"cannot resolve destination rule {rule}; supply --target-schema-without-add-json")
        if generated_parents and dst_level != "NONE" and key[:-1] not in parent_mappings:
            raise ValueError(f"cannot resolve generated database/schema mapping for {path}; supply --target-schema-without-add-json")
        parent = parent_mappings.get(key[:-1], key[:-1])
        if not parent:
            parent = parent_mappings.get(("ANY_SCHEMA",), parent_mappings.get(("ANY_DB",), ()))
        if dst_level == "NONE":
            parent = ()
        return parent + (transform_name(key[-1], rule),)

    def target_key(path):
        if not target_case_sensitive:
            return tuple(name.casefold() for name in path)
        return path

    removed_targets = {target_key(destination(path)): destination(path) for path in removed_paths}
    shared_targets = {target_key(destination(path)) for path in retained_paths}
    drop_targets = removed_targets.keys() - shared_targets
    seen_targets = set()

    def select_target(path):
        key = target_key(path)
        seen_targets.add(key)
        return key in drop_targets

    retained_target, _ = partition_subscription(target, select_target)
    if seen_targets:
        for path in removed_paths:
            dest = target_key(destination(path))
            if dest not in seen_targets and ((path[:1] if db_topic else path) not in table_targets
                                             or any(t[-1] == dest[-1] for t in seen_targets)):
                raise ValueError(f"cannot match destination for {path}; specify source=target or --target-schema-without-add-json")
    result["dstSchemaWithoutAdd"] = compare_obj_json(retained_target)
    if oracle_cleanup:
        # The staging cleanup handlers identify a table by schema and table name.
        shared_staging = {path[-2:] for path in shared_targets}
        tables = []
        for key in sorted(drop_targets):
            if key[-2:] in shared_staging:
                continue
            path = removed_targets[key]
            if len(path) != (3 if dst_type == "Oracle" else 2):
                raise ValueError(f"cannot resolve Oracle destination {path}; supply targetReduceConfig")
            tables.append({"targetDb": path[0], "targetSchema": path[1] if len(path) == 3 else None, "targetTable": path[-1]})
        if tables:
            cleanup = build_schema_json(dst_type, "DB_SCHEMA" if dst_type == "Oracle" else "DB", tables, "target")
            result["targetReduceConfig"] = compare_obj_json(cleanup)
    return result


def build_edit_job_payload(args, client):
    if not (
        args.add_table
        or args.add_table_map
        or args.remove_table
        or args.reduce_config_json
        or args.payload_json
        or args.source_schema_without_add_json
        or args.target_schema_without_add_json
        or args.mapping_without_add_json
        or args.processor_without_add_json
        or args.add_processor_config_json
    ):
        raise ValueError("edit-job needs --add-table/--add-table-map or a raw/override JSON payload")

    job_id = parse_int(args.job_id, "dataJobId")
    job = query_job(client, job_id)
    src_ds = job_source_ds(job)
    dst_ds = job_target_ds(job)
    src_type = normalize_ds_type(args.source_type) if args.source_type else data_source_type(src_ds)
    dst_type = normalize_ds_type(args.target_type) if args.target_type else data_source_type(dst_ds)
    schema = query_job_schema(client, job_id, src_type, dst_type)

    extra = read_json_arg(args.payload_json, {})

    payload = {
        "dataJobId": job_id,
        "structMigration": bool(args.struct_migration),
        "initialSync": bool(args.initial_sync),
        "mappingConfigWithoutAdd": schema.get("mappingConfig") or "[]",
        "srcSchemaWithoutAdd": schema.get("sourceSchema") or "[]",
        "dstSchemaWithoutAdd": schema.get("targetSchema") or "[]",
        "processorConfsWithoutAdd": [],
        "addProcessorConfs": read_json_arg(args.add_processor_config_json, []),
    }

    if "processorConfsWithoutAdd" not in extra:
        if args.processor_without_add_json:
            processors = read_json_arg(args.processor_without_add_json)
        else:
            processors = json.loads(job.get("processorConfigListJson") or "[]")
            if processors is None:
                processors = []
        if not isinstance(processors, list):
            raise ValueError("processorConfsWithoutAdd must be a JSON array")
        payload["processorConfsWithoutAdd"] = processors

    if args.add_table or args.add_table_map:
        cluster_id = args.cluster_id or job.get("clusterId")
        if not cluster_id:
            cluster_id = resolve_cluster_id(args, client)
        src_host_type = host_type_value(args.source_host_type or src_ds.get("hostType"))
        dst_host_type = host_type_value(args.target_host_type or dst_ds.get("hostType"))
        schema_rule = fetch_schema_mapping_rule(client, src_type, dst_type, dst_ds.get("deployType"))
        src_level = schema_level(src_type, schema_rule, "source")
        dst_level = schema_level(dst_type, schema_rule, "target")
        table_rules = fetch_table_mapping_rules(client, cluster_id, src_type, dst_type, dst_ds.get("id"), dst_host_type, args.table_select_mode)
        column_rules = fetch_column_mapping_rules(client, src_type, dst_type)
        table_rule = args.table_rule or choose_default_rule(table_rules, schema_rule.get("mappingRule") or "MIRROR")
        column_rule = args.column_rule or choose_default_rule(column_rules, "MIRROR")
        table_args = SimpleNamespace(
            table=args.add_table,
            table_map=args.add_table_map,
            column_map=args.column_map,
            source_db=args.source_db,
            source_schema=args.source_schema,
            target_db=args.target_db,
            target_schema=args.target_schema,
            target_table=args.target_table,
            table_mapping_method=args.table_mapping_method,
        )
        tables = parse_table_args(table_args, src_level, dst_level, schema_rule, table_rule)
        parse_column_maps(table_args, tables)
        enrich_source_columns(client, src_ds.get("id"), cluster_id, src_type, src_level, src_host_type, tables, False)
        source_add = build_schema_json(src_type, src_level, tables, "source", False)
        validate_source_schema_columns(src_type, source_add)
        target_add = build_schema_json(dst_type, dst_level, tables, "target", args.auto_create_target)
        add_mapping = build_mapping_def(src_type, dst_type, src_level, dst_level, schema_rule, table_rule, column_rule, tables, table_args)
        payload["sourceAddConfig"] = json.dumps(source_add, ensure_ascii=False, separators=(",", ":"))
        payload["targetAddConfig"] = json.dumps(target_add, ensure_ascii=False, separators=(",", ":")) if target_add is not None else None
        payload["addMappingConfig"] = json.dumps(add_mapping, ensure_ascii=False, separators=(",", ":"))

    overrides = {
        key: json_string_arg(value)
        for key, value in (
            ("srcSchemaWithoutAdd", args.source_schema_without_add_json),
            ("dstSchemaWithoutAdd", args.target_schema_without_add_json),
            ("mappingConfigWithoutAdd", args.mapping_without_add_json),
            ("reduceConfig", args.reduce_config_json),
        )
        if value
    }
    if args.remove_table:
        schema_rule = fetch_schema_mapping_rule(client, src_type, dst_type, dst_ds.get("deployType"))
        src_level = schema_level(src_type, schema_rule, "source")
        dst_level = schema_level(dst_type, schema_rule, "target")
        payload.update(removed_subscription(args, schema, src_level, dst_level, dst_type, {**overrides, **extra}, job.get("dstDsCaseSensitive")))
    payload.update(overrides)
    deep_merge(payload, extra)
    return payload


def edit_job_cmd(args, client):
    path = UPDATE_TRANSFER_OBJECT_FOR_FULL_PATH if args.full else UPDATE_TRANSFER_OBJECT_PATH
    payload = build_edit_job_payload(args, client)
    if args.dry_run:
        print_json({"path": path, "payload": mask_payload(payload)})
        return 0
    response = client.post_json(path, payload)
    success_data(client, response, "edit data job")
    print("Data job edit submitted, id=" + str(payload["dataJobId"]))
    return 0


def manual_merge_edit_job_cmd(args, client):
    payload = {"dataJobId": parse_int(args.job_id, "dataJobId")}
    if args.dry_run:
        print_json({"path": MANUAL_MERGE_EDIT_JOB_PATH, "payload": payload})
        return 0
    response = client.post_json(MANUAL_MERGE_EDIT_JOB_PATH, payload)
    success_data(client, response, "manual merge edit job")
    print("Manual merge edit job succeeded, id=" + str(payload["dataJobId"]))
    return 0


def time_schedule_cmd(args, client):
    paths = {
        "pause": (PAUSE_TIME_SCHEDULE_PATH, "pause data job time schedule"),
        "resume": (RESUME_TIME_SCHEDULE_PATH, "resume data job time schedule"),
        "start": (START_TIME_SCHEDULE_JOB_PATH, "start data job time schedule job"),
    }
    path, action = paths[args.action]
    payload = {"jobId": parse_int(args.job_id, "jobId")}
    if args.dry_run:
        print_json({"path": path, "payload": payload})
        return 0
    response = client.post_json(path, payload)
    success_data(client, response, action)
    print(action + " succeeded, id=" + str(payload["jobId"]))
    return 0


def manual_schedule_cmd(args, client):
    task_ids = parse_id_list(args.data_task_id, "dataTaskId")
    if len(task_ids) == 1:
        path = MANUAL_SCHEDULE_PATH
        payload = {
            "dataTaskId": task_ids[0],
            "oldWorkerId": parse_int(args.old_worker_id, "oldWorkerId"),
            "targetWorkerId": parse_int(args.target_worker_id, "targetWorkerId"),
        }
    else:
        path = MANUAL_BATCH_SCHEDULE_PATH
        payload = {
            "dataTaskIds": task_ids,
            "oldWorkerId": parse_int(args.old_worker_id, "oldWorkerId"),
            "targetWorkerId": parse_int(args.target_worker_id, "targetWorkerId"),
        }
    if args.dry_run:
        print_json({"path": path, "payload": payload})
        return 0
    response = client.post_json(path, payload)
    data = success_data(client, response, "manual schedule data task")
    print_json({"consoleTaskId": data})
    return 0


def list_specs_cmd(args, client):
    job_type, initial_sync, short_term_sync, _check_once, _struct_migration = resolve_job_mode(args)
    print_json(list_specs(client, job_type, initial_sync, short_term_sync))
    return 0


def data_source_meta_payload(ds, ds_id, cluster_id, host_type, host=None, ds_type=None):
    resolved_host, resolved_host_type = choose_test_host(ds, host_type, host)
    payload = {
        "dataSourceId": parse_int(ds_id, "dataSourceId"),
        "clusterId": cluster_id,
        "host": resolved_host,
        "hostType": resolved_host_type,
        "type": ds_type or data_source_type(ds),
    }
    if ds.get("dbName"):
        payload["dbName"] = ds.get("dbName")
    return payload


def list_dbs(client, ds_id, cluster_id, host_type=None, host=None):
    ds = query_datasource(client, ds_id)
    payload = data_source_meta_payload(ds, ds_id, cluster_id, host_type, host)
    response = client.post_json(LIST_DB_PATH, payload)
    return success_data(client, response, "list datasource dbs") or []


def list_tables(client, ds_id, cluster_id, db_name, schema_name=None, host_type=None, host=None, table_select_mode="LIST_ALL_AND_SELECT"):
    ds = query_datasource(client, ds_id)
    payload = data_source_meta_payload(ds, ds_id, cluster_id, host_type, host)
    payload["dbName"] = db_name
    if schema_name:
        payload["tableSchema"] = schema_name
    payload["tableSelectMode"] = table_select_mode
    response = client.post_json(LIST_TABLE_NEW_PATH, payload)
    return success_data(client, response, "list datasource tables") or []


def table_meta_arg(value, default_db=None, default_schema=None):
    parsed = parse_table_path(value, "DB_SCHEMA", default_db, default_schema)
    return {
        "dbName": parsed.get("db"),
        "schemaName": parsed.get("schema"),
        "tableName": parsed.get("table"),
    }


def table_meta_payload(ds, ds_id, cluster_id, host_type, host, tables, db_name=None, schema_name=None):
    payload = data_source_meta_payload(ds, ds_id, cluster_id, host_type, host)
    if db_name:
        payload["dbName"] = db_name
    table_metas = []
    for table in tables:
        meta = table_meta_arg(table, db_name, schema_name)
        if not meta.get("dbName") and db_name:
            meta["dbName"] = db_name
        table_metas.append(meta)
    payload["tableMetas"] = table_metas
    return payload


def list_columns(client, ds_id, cluster_id, tables, db_name=None, schema_name=None, host_type=None, host=None):
    ds = query_datasource(client, ds_id)
    payload = table_meta_payload(ds, ds_id, cluster_id, host_type, host, tables, db_name, schema_name)
    response = client.post_json(COLUMN_BATCH_LIST_PATH, payload)
    return success_data(client, response, "list datasource columns") or {}


def list_table_uniqs(client, ds_id, cluster_id, db_names, host_type=None, host=None):
    ds = query_datasource(client, ds_id)
    payload = data_source_meta_payload(ds, ds_id, cluster_id, host_type, host)
    payload["dbNames"] = db_names
    if len(db_names) == 1:
        payload["dbName"] = db_names[0]
    response = client.post_json(LIST_DB_TABLES_UNIQS_PATH, payload)
    return success_data(client, response, "list datasource table unique keys") or {}


def query_type_mapping(client, source_type, target_type, source_ds_id=None, target_ds_id=None):
    payload = {
        "srcDsType": source_type,
        "dstDsType": target_type,
    }
    if source_ds_id:
        payload["srcDsId"] = parse_int(source_ds_id, "srcDsId")
    if target_ds_id:
        payload["dstDsId"] = parse_int(target_ds_id, "dstDsId")
    response = client.post_json(TYPE_MAPPING_PATH, payload)
    return success_data(client, response, "query type mapping") or {}


def list_dbs_cmd(args, client):
    cluster_id = resolve_cluster_id(args, client)
    print_json(list_dbs(client, args.data_source_id, cluster_id, args.host_type, args.host))
    return 0


def list_tables_cmd(args, client):
    cluster_id = resolve_cluster_id(args, client)
    print_json(list_tables(client, args.data_source_id, cluster_id, args.db, args.schema, args.host_type, args.host, args.table_select_mode))
    return 0


def list_columns_cmd(args, client):
    cluster_id = resolve_cluster_id(args, client)
    print_json(list_columns(client, args.data_source_id, cluster_id, args.table, args.db, args.schema, args.host_type, args.host))
    return 0


def list_table_uniqs_cmd(args, client):
    cluster_id = resolve_cluster_id(args, client)
    print_json(list_table_uniqs(client, args.data_source_id, cluster_id, args.db, args.host_type, args.host))
    return 0


def resolve_type_mapping_types(args, client):
    if args.source_type:
        source_type = normalize_ds_type(args.source_type)
    elif args.source_ds_id:
        source_type = data_source_type(query_datasource(client, args.source_ds_id))
    else:
        raise ValueError("--source-type or --source-ds-id is required")

    if args.target_type:
        target_type = normalize_ds_type(args.target_type)
    elif args.target_ds_id:
        target_type = data_source_type(query_datasource(client, args.target_ds_id))
    else:
        raise ValueError("--target-type or --target-ds-id is required")
    return source_type, target_type


def type_mapping_cmd(args, client):
    source_type, target_type = resolve_type_mapping_types(args, client)
    print_json(query_type_mapping(client, source_type, target_type, args.source_ds_id, args.target_ds_id))
    return 0


def get_job_config_cmd(args, client):
    response = client.post_json(JOB_CONFIG_GET_PATH, {"dataJobId": parse_int(args.job_id, "dataJobId")})
    print_json(success_data(client, response, "get data job configs"))
    return 0


def list_job_config_tags_cmd(args, client):
    response = client.post_json(JOB_CONFIG_LIST_TAG_PATH, {})
    print_json(success_data(client, response, "list data job config tags"))
    return 0


def list_job_configs_cmd(args, client):
    payload = {"dataJobId": parse_int(args.job_id, "dataJobId")}
    if args.config_name:
        payload["configName"] = args.config_name
    if args.tag:
        payload["tagNameList"] = args.tag
    extra = read_json_arg(args.payload_json, {})
    deep_merge(payload, extra)
    response = client.post_json(JOB_CONFIG_LIST_PATH, payload)
    print_json(success_data(client, response, "list data job configs"))
    return 0


def update_job_configs_cmd(args, client):
    payload = read_json_arg(args.payload_json, None)
    if payload is None:
        payload = []
    elif isinstance(payload, dict):
        payload = [payload]
    for item in args.config or []:
        parts = item.split(":", 3)
        if len(parts) != 4:
            raise ValueError("--config expects name:endPointType:configType:value, got: " + item)
        name, endpoint_type, config_type, value = parts
        payload.append(
            {
                "dataJobId": parse_int(args.job_id, "dataJobId"),
                "configName": name,
                "endPointType": endpoint_type,
                "configType": config_type,
                "configValue": value,
                "needCreate": bool(args.need_create),
            }
        )
    if not payload:
        raise ValueError("--payload-json or --config is required")
    if args.dry_run:
        print_json({"path": JOB_CONFIG_UPDATE_PATH, "payload": payload})
        return 0
    response = client.post_json(JOB_CONFIG_UPDATE_PATH, payload)
    success_data(client, response, "update data job configs")
    print("Data job configs updated, id=" + str(args.job_id))
    return 0


def export_job_config_cmd(args, client):
    payload = {
        "exportType": args.export_type,
        "dataJobId": parse_int(args.job_id, "dataJobId"),
    }
    extra = read_json_arg(args.payload_json, {})
    deep_merge(payload, extra)
    if args.dry_run:
        print_json({"path": JOB_CONFIG_EXPORT_PATH, "payload": payload})
        return 0
    response = client.post_json(JOB_CONFIG_EXPORT_PATH, payload)
    print_json(success_data(client, response, "export data job config"))
    return 0


def job_config_template_cmd(args, client):
    path = JOB_CONFIG_TEMPLATE_PREVIEW_PATH if args.preview else JOB_CONFIG_TEMPLATE_UPDATE_PATH
    payload = {
        "dataJobId": parse_int(args.job_id, "dataJobId"),
        "jobKvConfigTemplId": parse_int(args.template_id, "jobKvConfigTemplId"),
    }
    if args.dry_run:
        print_json({"path": path, "payload": payload})
        return 0
    response = client.post_json(path, payload)
    data = success_data(client, response, "apply data job config template")
    print_json(data)
    return 0


def position_ops_cmd(args, client):
    src_type = normalize_ds_type(args.source_type) if args.source_type else None
    if not src_type and args.job_id:
        data = query_job(client, args.job_id)
        src_type = data_source_type(job_source_ds(data))
    if not src_type:
        raise ValueError("--source-type or --job-id is required")
    payload = {"taskId": parse_int(args.task_id, "taskId"), "srcDsType": src_type}
    response = client.post_json(WEBOP_INCRE_DATA_TASK_POS_OPS_PATH, payload)
    print_json(success_data(client, response, "query incremental position ops"))
    return 0


def fetch_current_pos_cmd(args, client):
    payload = {
        "taskId": parse_int(args.task_id, "taskId"),
        "posType": args.pos_type,
    }
    response = client.post_json(POSITION_FETCH_CURRENT_POS_PATH, payload)
    print_json(success_data(client, response, "fetch current position"))
    return 0


def update_incre_pos_cmd(args, client):
    payload = {
        "taskId": parse_int(args.task_id, "taskId"),
        "posType": args.pos_type,
    }
    scalar_fields = {
        "journalFile": args.journal_file,
        "filePosition": args.file_position,
        "gtidPosition": args.gtid_position,
        "positionTimestamp": args.position_timestamp,
        "serverId": args.server_id,
        "lsn": args.lsn,
        "scn": args.scn,
        "scnIndex": args.scn_index,
        "commonPosStr": maybe_read_value_file(args.common_pos_str) if args.common_pos_str else None,
        "dataId": args.data_id,
        "transactionId": args.transaction_id,
    }
    for key, value in scalar_fields.items():
        if value is not None:
            payload[key] = value
    extra = read_json_arg(args.payload_json, {})
    deep_merge(payload, extra)
    if args.dry_run:
        print_json({"path": POSITION_UPDATE_INCRE_POS_PATH, "payload": payload})
        return 0
    response = client.post_json(POSITION_UPDATE_INCRE_POS_PATH, payload)
    success_data(client, response, "update incremental position")
    print("Incremental position updated, taskId=" + str(payload["taskId"]))
    return 0


def reset_pos_to_current_cmd(args, client):
    payload = {
        "taskId": parse_int(args.task_id, "taskId"),
        "posTypes": args.pos_type,
    }
    if args.dry_run:
        print_json({"path": POSITION_RESET_POS_TO_CURRENT_PATH, "payload": payload})
        return 0
    response = client.post_json(POSITION_RESET_POS_TO_CURRENT_PATH, payload)
    success_data(client, response, "reset position to current")
    print("Position reset to current, taskId=" + str(payload["taskId"]))
    return 0


def reset_position_cmd(args, client):
    payload = {
        "taskId": parse_int(args.task_id, "taskId"),
        "resetTimeMillis": parse_int(args.reset_time_millis, "resetTimeMillis"),
        "clearPosition": bool(args.clear_position),
    }
    if args.verify_code:
        payload["verifyCode"] = args.verify_code
    if args.data_id:
        payload["dataId"] = parse_int(args.data_id, "dataId")
    extra = read_json_arg(args.payload_json, {})
    deep_merge(payload, extra)
    if args.dry_run:
        print_json({"path": POSITION_RESET_PATH, "payload": payload})
        return 0
    response = client.post_json(POSITION_RESET_PATH, payload)
    success_data(client, response, "reset position")
    print("Position reset, taskId=" + str(payload["taskId"]))
    return 0


def fetch_job_extra_configs(client, src_type, dst_type):
    response = client.post_json(WEBOP_EXTRA_CONFIGS_PATH, {"srcDsType": src_type, "dstDsType": dst_type})
    return success_data(client, response, "query job extra configs") or {}


def simple_value(value):
    if not isinstance(value, str):
        return value
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    return value


def default_extra_json(configs):
    result = {}
    for ops in (configs or {}).values():
        for op in ops or []:
            target = op.get("targetParameter")
            if not target:
                continue
            value = op.get("preFillValue")
            for option in op.get("options") or []:
                if option.get("defaultCheck"):
                    value = option.get("value")
                    break
            if value not in (None, ""):
                result[target] = simple_value(value)
    return result


def datasource_task_extra_json(client, data_source_id, ds_type):
    names = set(DATASOURCE_TASK_CONFIG_NAMES.get(ds_type) or set())
    if not names and ds_type not in DATASOURCE_TASK_CONFIG_NAMES:
        return {}
    configs = query_datasource_config(client, data_source_id)
    values = {item.get("configName"): item for item in configs or [] if item.get("configName")}
    proxy_mode = values.get("proxyMode", {}).get("configValue")
    if proxy_mode and str(proxy_mode).upper() != "NONE":
        names.update(PROXY_TASK_CONFIG_NAMES)

    result = {}
    for name in names:
        item = values.get(name) or {}
        if item.get("secret"):
            continue
        value = item.get("configValue")
        if value in (None, ""):
            continue
        result[name] = simple_value(value)
    return result


def resolve_extra_config_types(args, client):
    if args.source_type:
        src_type = normalize_ds_type(args.source_type)
    elif args.source_ds_id:
        src_type = data_source_type(query_datasource(client, args.source_ds_id))
    else:
        raise ValueError("--source-type or --source-ds-id is required")

    if args.target_type:
        dst_type = normalize_ds_type(args.target_type)
    elif args.target_ds_id:
        dst_type = data_source_type(query_datasource(client, args.target_ds_id))
    else:
        raise ValueError("--target-type or --target-ds-id is required")
    return src_type, dst_type


def job_extra_configs_cmd(args, client):
    src_type, dst_type = resolve_extra_config_types(args, client)
    configs = fetch_job_extra_configs(client, src_type, dst_type)
    if args.defaults:
        print_json(default_extra_json(configs))
    else:
        print_json(configs)
    return 0
