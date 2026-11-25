#!/usr/bin/env python3
import argparse
import json
import os
import re
from pathlib import Path


CORE_API_FILES = [
    "dataJob.js",
    "datasource.js",
    "constant.js",
    "position.js",
    "schedule.js",
    "webOp.js",
    "fsm.js",
    "dataJobGroup.js",
]

ENDPOINT_RE = re.compile(r"([A-Za-z0-9_]+)\s*:\s*['\"]([^'\"]+)['\"]")
CLOUDCANAL_RDP_API_FILES = {"datasource.js", "constant.js"}

INTENTIONAL_NOT_WRAPPED = {
    "/cloudcanal/console/api/v1/inner/datajob/activefsm",
    "/cloudcanal/console/api/v1/inner/datajob/activefsmbatch",
}


def api_files(frontend_dir, names=None):
    api_dir = frontend_dir / "src" / "services" / "http" / "api"
    if not api_dir.is_dir():
        raise FileNotFoundError(f"frontend API directory does not exist: {api_dir}")
    if names:
        paths = [api_dir / name for name in names]
        missing = [name for name, path in zip(names, paths) if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"missing frontend API files in {api_dir}: {', '.join(missing)}")
        return paths
    paths = sorted(path for path in api_dir.glob("*.js") if path.is_file())
    if not paths:
        raise FileNotFoundError(f"no JavaScript API files in {api_dir}")
    return paths


def normalize_endpoint(endpoint):
    if endpoint.startswith("cloudcanal/") or endpoint.startswith("rdp/"):
        return "/" + endpoint
    return endpoint


def is_console_endpoint(endpoint, api_file=None):
    normalized = normalize_endpoint(endpoint)
    if normalized.startswith("/cloudcanal/"):
        return True
    if normalized.startswith("/rdp/"):
        return api_file in CLOUDCANAL_RDP_API_FILES
    return False


def parse_frontend_api(frontend_dir, names=None):
    result = []
    seen = set()
    for path in api_files(frontend_dir, names):
        text = path.read_text(encoding="utf-8")
        for service, endpoint in ENDPOINT_RE.findall(text):
            if not is_console_endpoint(endpoint, path.name):
                continue
            endpoint = normalize_endpoint(endpoint)
            key = (service, endpoint, str(path))
            if key in seen:
                continue
            seen.add(key)
            result.append({"service": service, "endpoint": endpoint, "file": str(path), "apiFile": path.name})
    return result


def parse_skill_endpoints(skill_dir):
    result = set()
    for path in (skill_dir / "scripts" / "cc_console").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for endpoint in re.findall(r"['\"](/[A-Za-z0-9_./-]+)['\"]", text):
            result.add(endpoint)
    return result


def main():
    parser = argparse.ArgumentParser(description="Audit CloudCanal frontend API coverage by this skill.")
    parser.add_argument("--frontend-dir", default=os.environ.get("CLOUDCANAL_WEB_DIR", ""), help="Path to clouddm-web checkout.")
    parser.add_argument(
        "--skill-dir",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to cloudcanal-console-automation skill directory.",
    )
    parser.add_argument("--api-file", action="append", help="Limit to one frontend api file, e.g. dataJob.js. May repeat.")
    parser.add_argument("--core", action="store_true", help="Limit to core datasource/job operation API files.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    if not args.frontend_dir:
        raise SystemExit("ERROR: --frontend-dir or CLOUDCANAL_WEB_DIR is required")
    frontend_dir = Path(args.frontend_dir).expanduser().resolve()
    skill_dir = Path(args.skill_dir).expanduser().resolve()

    api_file_names = args.api_file or (CORE_API_FILES if args.core else None)
    try:
        frontend = parse_frontend_api(frontend_dir, api_file_names)
    except FileNotFoundError as exc:
        parser.error(str(exc))
    skill_endpoints = parse_skill_endpoints(skill_dir)
    rows = []
    for item in sorted(frontend, key=lambda row: (row["service"], row["endpoint"], row["apiFile"])):
        endpoint = item["endpoint"]
        if endpoint in skill_endpoints:
            status = "wrapped"
        elif endpoint in INTENTIONAL_NOT_WRAPPED:
            status = "intentional-not-wrapped"
        else:
            status = "call-service"
        rows.append(
            {
                "service": item["service"],
                "endpoint": endpoint,
                "status": status,
                "file": item["file"],
                "apiFile": item["apiFile"],
            }
        )

    summary = {
        "frontendApis": len(rows),
        "wrapped": sum(1 for row in rows if row["status"] == "wrapped"),
        "callService": sum(1 for row in rows if row["status"] == "call-service"),
        "intentionalNotWrapped": sum(1 for row in rows if row["status"] == "intentional-not-wrapped"),
    }
    if args.format == "json":
        print(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))
        return

    print("# CloudCanal Frontend Parity Audit")
    print()
    print(
        "- frontendApis: {frontendApis}\n- wrapped: {wrapped}\n- call-service fallback: {callService}\n- intentional-not-wrapped: {intentionalNotWrapped}".format(
            **summary
        )
    )
    print()
    print("| Status | Service | Endpoint | File |")
    print("| --- | --- | --- | --- |")
    for row in rows:
        print("| {status} | `{service}` | `{endpoint}` | `{apiFile}` |".format(**row))


if __name__ == "__main__":
    main()
