import json
import os
import re
from pathlib import Path

from cc_console.client import MultipartFile, json_part
from cc_console.datajob import CREATE_JOB_PATH
from cc_console.utils import mask_payload, maybe_read_value_file, print_json


CORE_API_FILES = [
    "dataJob.js",
    "datasource.js",
    "constant.js",
    "position.js",
    "schedule.js",
    "webOp.js",
    "dataJobGroup.js",
]

ENDPOINT_RE = re.compile(r"([A-Za-z0-9_]+)\s*:\s*['\"]([^'\"]+)['\"]")
CLOUDCANAL_RDP_API_FILES = {"datasource.js", "constant.js"}


def read_json_arg(value, default=None):
    if value in (None, ""):
        return default
    text = maybe_read_value_file(value)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("invalid JSON: " + str(e)) from e


def file_part(path):
    with open(path, "rb") as file_obj:
        return MultipartFile(file_obj.read(), os.path.basename(path))


def parse_kv(items, arg_name):
    result = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(arg_name + " expects name=value, got: " + item)
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(arg_name + " key can not be empty")
        result[key] = value
    return result


def parse_scalar(value):
    text = maybe_read_value_file(value)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def write_body(args, status, headers, body):
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(body)
        print_json({"status": status, "headers": headers, "output": str(output), "bytes": len(body)})
        return 0

    print(body.decode("utf-8", errors="replace"))
    return 0


def find_frontend_dir(explicit=None):
    values = [
        explicit,
        os.environ.get("CLOUDCANAL_WEB_DIR"),
        os.environ.get("CC_FRONTEND_DIR"),
    ]
    for value in values:
        if value:
            return Path(value).expanduser()

    for start in (Path.cwd(), Path(__file__).resolve()):
        current = start if start.is_dir() else start.parent
        for parent in (current, *current.parents):
            candidates = [parent, parent / "clouddm-web"]
            for candidate in candidates:
                if candidate.name == "clouddm-web" and candidate.exists():
                    return candidate
    return None


def _api_files(frontend_dir, api_files=None):
    api_dir = frontend_dir / "src" / "services" / "http" / "api"
    names = api_files or [path.name for path in sorted(api_dir.glob("*.js"))]
    return [api_dir / name for name in names]


def _is_console_endpoint(endpoint, api_file=None):
    normalized = _normalize_endpoint(endpoint)
    if normalized.startswith("/cloudcanal/"):
        return True
    if normalized.startswith("/rdp/"):
        return api_file in CLOUDCANAL_RDP_API_FILES
    return False


def _normalize_endpoint(endpoint):
    if endpoint.startswith("cloudcanal/") or endpoint.startswith("rdp/"):
        return "/" + endpoint
    return endpoint


def frontend_services(frontend_dir, api_files=None):
    result = {}
    for path in _api_files(frontend_dir, api_files):
        name = path.name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for service, endpoint in ENDPOINT_RE.findall(text):
            if not _is_console_endpoint(endpoint, name):
                continue
            endpoint = _normalize_endpoint(endpoint)
            result.setdefault(service, [])
            item = {"endpoint": endpoint, "file": str(path), "apiFile": name}
            if item not in result[service]:
                result[service].append(item)
    return result


def resolve_frontend_service(service, frontend_dir, api_files=None):
    if not frontend_dir:
        raise ValueError("--frontend-dir or CLOUDCANAL_WEB_DIR is required to resolve --service")
    frontend_dir = frontend_dir.resolve()
    services = frontend_services(frontend_dir, api_files)
    if service in services:
        matches = services[service]
        endpoints = sorted(set(item["endpoint"] for item in matches))
        if len(endpoints) == 1:
            return endpoints[0]
        hint = "; use --api-file to disambiguate: " + ", ".join(item["apiFile"] for item in matches)
        raise ValueError("frontend service is ambiguous: " + service + hint)
    matches = [name for name in services if service.lower() in name.lower()]
    hint = ""
    if matches:
        hint = "; similar services: " + ", ".join(matches[:10])
    raise ValueError("frontend service not found: " + service + hint)


def list_services_cmd(args):
    frontend_dir = find_frontend_dir(args.frontend_dir)
    if not frontend_dir:
        raise ValueError("--frontend-dir or CLOUDCANAL_WEB_DIR is required")
    api_files = args.api_file or (CORE_API_FILES if args.core else None)
    rows = []
    for service, items in sorted(frontend_services(frontend_dir.resolve(), api_files).items()):
        if args.filter and args.filter.lower() not in service.lower() and not any(args.filter.lower() in item["endpoint"].lower() for item in items):
            continue
        for item in items:
            rows.append({"service": service, **item})
    if args.format == "json":
        print_json(rows)
        return 0
    print("| Service | Endpoint | File |")
    print("| --- | --- | --- |")
    for row in rows:
        print("| `{service}` | `{endpoint}` | `{apiFile}` |".format(**row))
    return 0


def call_api_cmd(args, client):
    path = args.path
    if not path.startswith("/"):
        raise ValueError("--path must start with /")

    if not args.dry_run and args.response == "raw" and not args.output:
        raise ValueError("--response raw requires --output to avoid writing binary data to the terminal")

    if not args.dry_run and args.method == "POST" and path.partition("?")[0].rstrip("/") == CREATE_JOB_PATH:
        raise ValueError("Use create-job for job creation so the Console support matrix is checked first.")

    payload = read_json_arg(args.payload_json, {})
    for key, value in parse_kv(args.set, "--set").items():
        payload[key] = parse_scalar(value)

    if args.multipart:
        if args.method != "POST":
            raise ValueError("--multipart only supports POST")
        fields = {}
        for key, value in parse_kv(args.part, "--part").items():
            fields[key] = maybe_read_value_file(value)
        for key, value in parse_kv(args.json_part, "--json-part").items():
            fields[key] = json_part(read_json_arg(value, {}))
        for key, value in parse_kv(args.file_part, "--file-part").items():
            fields[key] = "<file:" + value + ">" if args.dry_run else file_part(value)
        if payload:
            fields[args.payload_part_name] = json.dumps(payload, ensure_ascii=False)
        if args.dry_run:
            printable = {"path": path, "multipart": True, "fields": sorted(fields.keys())}
            if payload:
                printable["payloadPartName"] = args.payload_part_name
                printable["payload"] = mask_payload(payload)
            print_json(printable)
            return 0
        if args.response == "json":
            print_json(client.post_multipart(path, fields))
            return 0
        status, headers, body = client.post_multipart_raw(path, fields)
        return write_body(args, status, headers, body)

    if args.dry_run:
        print_json({"method": args.method, "path": path, "payload": mask_payload(payload)})
        return 0

    if args.method == "GET":
        if args.response == "json":
            print_json(client.get_json(path, payload))
            return 0
        status, headers, body = client.get_raw(path, payload)
        return write_body(args, status, headers, body)

    if args.response == "json":
        print_json(client.post_json(path, payload))
        return 0
    status, headers, body = client.post_json_raw(path, payload)
    return write_body(args, status, headers, body)


def call_service_cmd(args, client):
    args.path = resolve_frontend_service(args.service, find_frontend_dir(args.frontend_dir), args.api_file)
    return call_api_cmd(args, client)
