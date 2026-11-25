import json
import os

from cc_console.clusters import resolve_cluster_id
from cc_console.client import ApiError, MultipartFile
from cc_console.utils import (
    looks_sensitive,
    mask_payload,
    maybe_read_value_file,
    normalize_bool,
    parse_int,
    parse_kv_overrides,
    print_json,
    prompt_line,
    validate_json_config,
)


DS_TYPE_ALIASES = {
    "mysql": "MySQL",
    "auroramysql": "AuroraMySQL",
    "gaussdbformysql": "GaussDBForMySQL",
    "mariadb": "MariaDB",
    "maridb": "MariaDB",
    "polardbmysql": "PolarDbMySQL",
    "polardbpg": "PolarDBPg",
    "polarmysql": "PolarDbMySQL",
    "polardb": "PolarDbMySQL",
    "drds": "DRDS",
    "polardbx": "PolarDbX",
    "tdsqlmysql": "TdsqlMySQL",
    "tdsqlcmysql": "TdsqlCMySQL",
    "tidb": "TiDB",
    "oceanbase": "OceanBase",
    "ob": "OceanBase",
    "oracle": "Oracle",
    "starrocks": "StarRocks",
    "sr": "StarRocks",
    "greenplum": "Greenplum",
    "gp": "Greenplum",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "rocketmq": "RocketMQ",
    "rmq": "RocketMQ",
    "clickhouse": "ClickHouse",
    "ck": "ClickHouse",
    "db2": "Db2",
    "opengauss": "GaussDBForOpenGauss",
    "opengaussdb": "GaussDBForOpenGauss",
    "gaussdbforopengauss": "GaussDBForOpenGauss",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "pg": "PostgreSQL",
    "redis": "Redis",
    "kafka": "Kafka",
    "sqlserver": "SQLServer",
    "sql-server": "SQLServer",
    "mssql": "SQLServer",
    "hana": "Hana",
    "hologres": "Hologres",
    "dameng": "Dameng",
    "dm": "Dameng",
    "kingbase": "KingbaseES",
    "kingbasees": "KingbaseES",
    "vastbase": "Vastbase",
    "vastbaseg100": "Vastbase",
    "automq": "AutoMQ",
    "amazonmsk": "AmazonMSK",
    "msk": "AmazonMSK",
    "rabbitmq": "RabbitMQ",
    "pulsar": "Pulsar",
    "elasticache": "ElastiCache",
    "elasticsearch": "ElasticSearch",
    "es": "ElasticSearch",
    "documentdb": "DocumentDB",
    "dynamodb": "DynamoDB",
    "kudu": "Kudu",
    "hudi": "Hudi",
    "iceberg": "Iceberg",
    "paimon": "Paimon",
    "deltalake": "DeltaLake",
    "maxcompute": "MaxCompute",
    "datalakeformation": "DataLakeFormation",
    "tunnel": "Tunnel",
    "ossfile": "OssFile",
    "s3file": "S3File",
    "sshfile": "SshFile",
    "googledrive": "GoogleDrive",
    "doris": "Doris",
    "selectdb": "SelectDB",
    "hive": "Hive",
    "cloudberry": "Cloudberry",
    "redshift": "Redshift",
    "aurorapostgresql": "AuroraPostgreSQL",
    "aurorapg": "AuroraPostgreSQL",
    "hologres": "Hologres",
    "snowflake": "Snowflake",
    "spanner": "Spanner",
    "gaussdb": "GaussDB",
    "yuque": "Yuque",
    "ragapi": "RagApi",
    "bedrock": "Bedrock",
    "lindorm": "Lindorm",
    "greptimedb": "GreptimeDB",
    "tdengine": "TDengine",
    "openai": "OpenAI",
    "dashscope": "DashScope",
    "huggingface": "HuggingFace",
    "cohere": "Cohere",
    "deepseek": "DeepSeek",
    "localai": "LocalAI",
    "ollama": "Ollama",
    "zhipuai": "ZhipuAI",
    "anthropic": "Anthropic",
}

DEFAULT_PORTS = {
    "MySQL": 3306,
    "AuroraMySQL": 3306,
    "GaussDBForMySQL": 3306,
    "MariaDB": 3306,
    "PolarDbMySQL": 3306,
    "TdsqlMySQL": 3306,
    "TdsqlCMySQL": 3306,
    "TiDB": 4000,
    "OceanBase": 2881,
    "Oracle": 1521,
    "StarRocks": 9030,
    "Greenplum": 5432,
    "MongoDB": 27017,
    "RocketMQ": 9876,
    "ClickHouse": 8123,
    "Db2": 50000,
    "GaussDBForOpenGauss": 5432,
    "PostgreSQL": 5432,
    "Redis": 6379,
    "ElastiCache": 6379,
    "Kafka": 9092,
    "AutoMQ": 9092,
    "AmazonMSK": 9092,
    "RabbitMQ": 5672,
    "Pulsar": 6650,
    "SQLServer": 1433,
    "Hana": 39017,
    "Hologres": 80,
    "Dameng": 5236,
    "KingbaseES": 54321,
    "Vastbase": 5432,
    "ElasticSearch": 9200,
    "MongoDB": 27017,
    "DocumentDB": 27017,
    "DynamoDB": 8000,
    "Doris": 9030,
    "SelectDB": 9030,
    "GreptimeDB": 4002,
    "TDengine": 6041,
    "Lindorm": 30020,
    "Redshift": 5439,
    "Cloudberry": 5432,
}

SECURITY_TYPES_WITHOUT_USER = ("NONE", "ONLY_PASSWD", "AK_SK", "CLOUD_CREDENTIAL_JSON")

CREATE_PATH = "/rdp/console/api/v1/datasource/add"
DELETE_PATH = "/rdp/console/api/v1/datasource/delete"
LIST_BY_CONDITION_PATH = "/rdp/console/api/v1/datasource/listbycondition"
QUERY_DS_PATH = "/rdp/console/api/v1/datasource/queryds"
QUERY_DS_CONFIG_PATH = "/rdp/console/api/v1/datasource/querydsconfig"
KV_DEF_PATH = "/rdp/console/api/v1/datasource/dsKvConfigDef"
KV_CONFIG_PATH = "/rdp/console/api/v1/datasource/dsKvConfig"
QUERY_LLM_CONFIG_PATH = "/rdp/console/api/v1/datasource/queryllmconfig"
TEST_CONNECTION_PATH = "/cloudcanal/console/api/v1/inner/datasource/connection"
UPDATE_DESC_PATH = "/rdp/console/api/v1/datasource/updatedatasourcedesc"
UPDATE_ACCOUNT_PATH = "/rdp/console/api/v1/datasource/updateaccountandpassword"
UPDATE_AK_SK_PATH = "/rdp/console/api/v1/datasource/updatealiyunrdsaksk"
DELETE_ACCOUNT_PATH = "/rdp/console/api/v1/datasource/deleteaccount"
UPDATE_PUBLIC_HOST_PATH = "/rdp/console/api/v1/datasource/updatepublichost"
UPDATE_PRIVATE_HOST_PATH = "/rdp/console/api/v1/datasource/updateprivatehost"
UPSERT_DS_CONFIG_PATH = "/rdp/console/api/v1/datasource/upsertdsconfig"


def normalize_ds_type(value):
    if not value:
        raise ValueError("datasource type is required")
    key = value.strip().lower()
    if key in DS_TYPE_ALIASES:
        return DS_TYPE_ALIASES[key]
    for ds_type in DS_TYPE_ALIASES.values():
        if ds_type.lower() == key:
            return ds_type
    raise ValueError("unsupported datasource type: " + value)


def normalize_connect_type(ds_type, value):
    if value:
        return value.strip().upper()
    if ds_type == "Oracle":
        return "ORACLE_SID"
    return None


def normalize_host_type(value):
    if not value:
        return None
    value = value.strip().upper()
    if value not in ("PRIVATE", "PUBLIC"):
        raise ValueError("unsupported host type: " + value)
    return value


def default_port(ds_type):
    return DEFAULT_PORTS.get(ds_type)


def read_json_arg(value, default=None):
    if value in (None, ""):
        return default
    text = maybe_read_value_file(value)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("invalid JSON: " + str(e)) from e


def requires_user(args):
    return (args.security_type or "").upper() not in SECURITY_TYPES_WITHOUT_USER


def fetch_kv_defs(client, ds_type, deploy_type):
    payload = {
        "dataSourceType": ds_type,
        "deployEnvType": deploy_type,
    }
    response = client.post_json(KV_DEF_PATH, payload)
    return client.ensure_success(response, "query datasource kv definitions") or []


def query_datasource(client, data_source_id):
    response = client.post_json(QUERY_DS_PATH, {"dataSourceId": data_source_id})
    data = client.ensure_success(response, "query datasource")
    if not data:
        raise ApiError("query datasource returned empty data")
    return data


def query_datasource_config(client, data_source_id, payload_extra=None):
    payload = {"dataSourceId": parse_int(data_source_id, "dataSourceId")}
    payload.update(payload_extra or {})
    response = client.post_json(QUERY_DS_CONFIG_PATH, payload)
    return client.ensure_success(response, "query datasource config") or []


def choose_test_host(ds, preferred_host_type=None, explicit_host=None):
    if explicit_host:
        host_type = normalize_host_type(preferred_host_type) or normalize_host_type(ds.get("hostType")) or "PRIVATE"
        return explicit_host, host_type

    host_type = normalize_host_type(preferred_host_type) or normalize_host_type(ds.get("hostType"))
    if host_type == "PUBLIC":
        return ds.get("publicHost") or ds.get("host"), "PUBLIC"
    if host_type == "PRIVATE":
        return ds.get("privateHost") or ds.get("host"), "PRIVATE"

    if ds.get("privateHost"):
        return ds.get("privateHost"), "PRIVATE"
    if ds.get("publicHost"):
        return ds.get("publicHost"), "PUBLIC"
    return ds.get("host"), "PRIVATE"


def test_connection(client, data_source_id, cluster_id, host=None, host_type=None):
    ds = query_datasource(client, data_source_id)
    resolved_host, resolved_host_type = choose_test_host(ds, host_type, host)
    if not resolved_host:
        raise ApiError("datasource host is empty, dataSourceId=" + str(data_source_id))

    payload = {
        "dataSourceId": data_source_id,
        "clusterId": cluster_id,
        "host": resolved_host,
        "hostType": resolved_host_type,
    }
    response = client.post_json(TEST_CONNECTION_PATH, payload)
    client.ensure_success(response, "test datasource connection")
    print("Datasource connection ok, id=" + str(data_source_id) + ", clusterId=" + str(cluster_id) + ", host=" + resolved_host)


def build_kv_configs(defs, overrides, non_interactive, strict_required):
    configs = []
    if not defs:
        return configs

    print("\nDatasource extra configs from server:")
    for config in defs:
        name = config.get("configName")
        if not name:
            continue
        default = config.get("defaultValue")
        required = bool(config.get("valueRequire"))
        conf_type = config.get("confValType") or "TEXT"
        value_advance = config.get("valueAdvance")
        description = config.get("description")

        if name in overrides:
            value = maybe_read_value_file(overrides[name])
        elif non_interactive:
            value = default or ""
        else:
            detail = name
            hints = []
            if conf_type:
                hints.append(conf_type)
            if required:
                hints.append("required")
            if value_advance:
                hints.append("hint=" + str(value_advance))
            if description:
                hints.append("desc=" + str(description))
            if hints:
                detail += " (" + ", ".join(hints) + ")"
            value = prompt_line(detail, default=default, required=False, sensitive=looks_sensitive(name))

        if strict_required and required and value == "":
            raise ValueError("missing required extra config: " + name)
        if conf_type == "BOOLEAN":
            value = normalize_bool(value)
        elif conf_type == "JSON":
            value = validate_json_config(name, value)

        configs.append({"configName": name, "configValue": value})
    return configs


def normalize_host(ds_type, host, port, db_name):
    host = host.strip()
    if not host:
        raise ValueError("host is required")

    if ds_type == "Oracle":
        if host.startswith("("):
            return host
        if host.count(":") >= 2:
            return host
        if host.count(":") == 1:
            return host + ":" + db_name if db_name else host
        port = port or default_port(ds_type)
        return host + ":" + str(port) + (":" + db_name if db_name else "")

    if host.count(":") >= 1:
        return host
    port = port or default_port(ds_type)
    return host + ":" + str(port) if port else host


def prompt_missing_base_args(args, ds_type):
    if not args.host:
        args.host = prompt_line("Datasource host", required=True)
    if args.port is None:
        default = default_port(ds_type)
        value = prompt_line("Datasource port", default=default, required=False)
        args.port = int(value) if value else None
    if not args.db:
        args.db = prompt_line("Default database/SID/service", required=(ds_type == "Oracle"))
    if requires_user(args) and not args.user:
        args.user = prompt_line("Account", required=True)
    if (args.security_type or "").upper() != "NONE" and args.password is None:
        args.password = prompt_line("Password", required=False, sensitive=True)
    if not args.desc:
        args.desc = prompt_line("Datasource description", default=ds_type + "-" + args.host, required=False)


def validate_base_args(args, ds_type):
    missing = []
    if not args.host:
        missing.append("--host")
    if requires_user(args) and not args.user:
        missing.append("--user")
    if ds_type == "Oracle" and not args.db and not (args.host and args.host.count(":") >= 2):
        missing.append("--db")
    if missing:
        raise ValueError("missing required args in non-interactive mode: " + ", ".join(missing))


def file_part(path):
    if not path:
        return ""
    with open(path, "rb") as file_obj:
        return MultipartFile(file_obj.read(), os.path.basename(path))


def build_add_payload(args, ds_type, kv_configs):
    private_host = args.private_host
    public_host = args.public_host
    normalized = normalize_host(ds_type, args.host, args.port, args.db)

    if not private_host and not public_host:
        if args.host_type == "public":
            public_host = normalized
        else:
            private_host = normalized

    selected_host = private_host or public_host
    selected_host_type = "PUBLIC" if not private_host and public_host else "PRIVATE"
    account = args.user
    if ds_type == "Oracle" and args.as_sysdba and account and " as " not in account.lower():
        account += " as SYSDBA"
    payload = {
        "deployType": args.deploy_type,
        "region": args.region,
        "type": ds_type,
        "dbName": args.db or "",
        "host": selected_host,
        "privateHost": private_host,
        "publicHost": public_host,
        "hostType": selected_host_type,
        "instanceDesc": args.desc,
        "account": account,
        "password": args.password or "",
        "securityType": args.security_type,
        "infoFetchType": args.info_fetch_type,
        "accessKey": args.access_key,
        "secretKey": args.secret_key,
        "securityFilePassword": args.security_file_password,
        "clientSecurityFilePassword": args.client_security_file_password,
        "secretFilePassword": args.secret_file_password,
        "clientTrustStorePassword": args.client_trust_store_password,
    }

    connect_type = normalize_connect_type(ds_type, args.connect_type)
    if connect_type:
        payload["connectType"] = connect_type
    if args.instance_id:
        payload["instanceId"] = args.instance_id
    if args.version:
        payload["version"] = args.version
    if args.driver:
        payload["driver"] = args.driver
    if args.bind_cluster_id is not None:
        payload["bindClusterId"] = args.bind_cluster_id
    if args.env_id is not None:
        payload["envId"] = args.env_id
    if kv_configs:
        payload["dsKvConfigs"] = kv_configs
    payload = {key: value for key, value in payload.items() if value is not None}
    return payload


def create_datasource_cmd(args, client):
    ds_type = normalize_ds_type(args.type)
    if not args.non_interactive:
        prompt_missing_base_args(args, ds_type)
    else:
        validate_base_args(args, ds_type)

    overrides = parse_kv_overrides(args.set)
    kv_defs = fetch_kv_defs(client, ds_type, args.deploy_type)
    kv_configs = build_kv_configs(kv_defs, overrides, args.non_interactive, args.strict_required)
    payload = build_add_payload(args, ds_type, kv_configs)

    if args.dry_run:
        print("\nDry run payload:")
        print_json(mask_payload(payload))
        return 0

    response = client.post_multipart(
        CREATE_PATH,
        {
            "secretFile": file_part(args.secret_file),
            "securityFile": file_part(args.security_file),
            "clientSecurityFile": file_part(args.client_security_file),
            "DataSourceAddData": json.dumps(payload, ensure_ascii=False),
        },
    )
    ds_id = client.ensure_success(response, "create datasource")
    print("Datasource created, id=" + str(ds_id))
    if args.test_after_add:
        cluster_id = resolve_cluster_id(args, client)
        test_connection(client, parse_int(ds_id, "dataSourceId"), cluster_id, args.test_host, args.test_host_type)
    return 0


def query_kv_defs_cmd(args, client):
    ds_type = normalize_ds_type(args.type)
    print_json(fetch_kv_defs(client, ds_type, args.deploy_type))
    return 0


def list_datasources_cmd(args, client):
    payload = read_json_arg(args.payload_json, {})
    optional_fields = {
        "type": normalize_ds_type(args.type) if args.type else None,
        "dataSourceType": normalize_ds_type(args.data_source_type) if args.data_source_type else None,
        "deployType": args.deploy_type,
        "instanceDesc": args.desc,
        "lifeCycleState": args.life_cycle_state,
        "useVisibility": args.use_visibility,
        "loadApproInfo": args.load_appro_info,
    }
    for key, value in optional_fields.items():
        if value not in (None, ""):
            payload[key] = value
    response = client.post_json(LIST_BY_CONDITION_PATH, payload)
    print_json(client.ensure_success(response, "list datasources"))
    return 0


def query_datasource_cmd(args, client):
    print_json(query_datasource(client, parse_int(args.data_source_id, "dataSourceId")))
    return 0


def query_datasource_config_cmd(args, client):
    print_json(query_datasource_config(client, args.data_source_id, read_json_arg(args.payload_json, {})))
    return 0


def query_datasource_kv_config_cmd(args, client):
    payload = {"dataSourceId": parse_int(args.data_source_id, "dataSourceId")}
    payload.update(read_json_arg(args.payload_json, {}))
    response = client.post_json(KV_CONFIG_PATH, payload)
    print_json(client.ensure_success(response, "query datasource kv config"))
    return 0


def query_llm_config_cmd(args, client):
    payload = {
        "dataSourceId": parse_int(args.data_source_id, "dataSourceId"),
    }
    if args.data_source_type:
        payload["dataSourceType"] = normalize_ds_type(args.data_source_type)
    payload.update(read_json_arg(args.payload_json, {}))
    response = client.post_json(QUERY_LLM_CONFIG_PATH, payload)
    print_json(client.ensure_success(response, "query LLM datasource config"))
    return 0


def delete_datasource_cmd(args, client):
    data_source_id = parse_int(args.data_source_id, "dataSourceId")
    if not args.yes:
        answer = prompt_line("Delete datasource " + str(data_source_id) + "? type yes to continue", required=True)
        if answer != "yes":
            print("Cancelled")
            return 1

    response = client.post_json(DELETE_PATH, {"dataSourceId": data_source_id})
    client.ensure_success(response, "delete datasource")
    print("Datasource deleted, id=" + str(data_source_id))
    return 0


def test_datasource_cmd(args, client):
    data_source_id = parse_int(args.data_source_id, "dataSourceId")
    cluster_id = resolve_cluster_id(args, client)
    test_connection(client, data_source_id, cluster_id, args.host, args.host_type)
    return 0


def update_datasource_desc_cmd(args, client):
    payload = {"dataSourceId": parse_int(args.data_source_id, "dataSourceId"), "instanceDesc": args.desc}
    if args.dry_run:
        print_json({"path": UPDATE_DESC_PATH, "payload": payload})
        return 0
    response = client.post_json(UPDATE_DESC_PATH, payload)
    client.ensure_success(response, "update datasource desc")
    print("Datasource desc updated, id=" + str(payload["dataSourceId"]))
    return 0


def update_datasource_host_cmd(args, client):
    data_source_id = parse_int(args.data_source_id, "dataSourceId")
    host_type = normalize_host_type(args.host_type)
    if host_type == "PUBLIC":
        path = UPDATE_PUBLIC_HOST_PATH
        payload = {"dataSourceId": data_source_id, "publicHost": args.host}
    else:
        path = UPDATE_PRIVATE_HOST_PATH
        payload = {"dataSourceId": data_source_id, "privateHost": args.host}
    if args.dry_run:
        print_json({"path": path, "payload": payload})
        return 0
    response = client.post_json(path, payload)
    client.ensure_success(response, "update datasource host")
    print("Datasource " + host_type.lower() + " host updated, id=" + str(data_source_id))
    return 0


def update_datasource_account_cmd(args, client):
    payload = {
        "dataSourceId": parse_int(args.data_source_id, "dataSourceId"),
        "userName": args.user,
        "password": args.password or "",
        "securityType": args.security_type,
    }
    optional_fields = {
        "accessKey": args.access_key,
        "secretKey": args.secret_key,
        "securityFilePassword": args.security_file_password,
        "secretFilePassword": args.secret_file_password,
        "clientSecurityFilePassword": args.client_security_file_password,
        "clientTrustStorePassword": args.client_trust_store_password,
    }
    for key, value in optional_fields.items():
        if value not in (None, ""):
            payload[key] = value
    extra = json.loads(maybe_read_value_file(args.payload_json)) if args.payload_json else {}
    payload.update(extra)
    if args.dry_run:
        print_json({"path": UPDATE_ACCOUNT_PATH, "payload": mask_payload(payload)})
        return 0
    response = client.post_multipart(
        UPDATE_ACCOUNT_PATH,
        {
            "DataSourceUpdateData": json.dumps(payload, ensure_ascii=False),
            "securityFile": file_part(args.security_file),
            "clientSecurityFile": file_part(args.client_security_file),
            "secretFile": file_part(args.secret_file),
        },
    )
    client.ensure_success(response, "update datasource account")
    print("Datasource account updated, id=" + str(payload["dataSourceId"]))
    return 0


def update_datasource_aksk_cmd(args, client):
    payload = {
        "dataSourceId": parse_int(args.data_source_id, "dataSourceId"),
        "accessKey": args.access_key,
        "secretKey": args.secret_key,
    }
    if args.dry_run:
        print_json({"path": UPDATE_AK_SK_PATH, "payload": mask_payload(payload)})
        return 0
    response = client.post_json(UPDATE_AK_SK_PATH, payload)
    client.ensure_success(response, "update datasource ak/sk")
    print("Datasource ak/sk updated, id=" + str(payload["dataSourceId"]))
    return 0


def delete_datasource_account_cmd(args, client):
    payload = {"dataSourceId": parse_int(args.data_source_id, "dataSourceId")}
    if args.dry_run:
        print_json({"path": DELETE_ACCOUNT_PATH, "payload": payload})
        return 0
    response = client.post_json(DELETE_ACCOUNT_PATH, payload)
    client.ensure_success(response, "delete datasource account")
    print("Datasource account deleted, id=" + str(payload["dataSourceId"]))
    return 0


def upsert_datasource_config_cmd(args, client):
    update_configs = {}
    need_create_configs = {}
    for item in args.set or []:
        if "=" not in item:
            raise ValueError("--set expects key=value, got: " + item)
        key, value = item.split("=", 1)
        update_configs[key.strip()] = maybe_read_value_file(value)
    for item in args.create or []:
        if "=" not in item:
            raise ValueError("--create expects key=value, got: " + item)
        key, value = item.split("=", 1)
        need_create_configs[key.strip()] = maybe_read_value_file(value)
    payload = {
        "dataSourceId": parse_int(args.data_source_id, "dataSourceId"),
        "updateConfigs": update_configs,
        "needCreateConfigs": need_create_configs,
    }
    if args.payload_json:
        payload.update(json.loads(maybe_read_value_file(args.payload_json)))
    if not payload.get("updateConfigs") and not payload.get("needCreateConfigs"):
        raise ValueError("--set, --create, or --payload-json with configs is required")
    if args.dry_run:
        print_json({"path": UPSERT_DS_CONFIG_PATH, "payload": mask_payload(payload)})
        return 0
    response = client.post_json(UPSERT_DS_CONFIG_PATH, payload)
    client.ensure_success(response, "upsert datasource config")
    print("Datasource configs upserted, id=" + str(payload["dataSourceId"]))
    return 0
