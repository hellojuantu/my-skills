#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from cc_console.db_adapters import ADAPTERS


def frontend_types(frontend_dir):
    group_file = frontend_dir / "src" / "views" / "dataSourceGroup.json"
    if not group_file.exists():
        raise SystemExit("ERROR: dataSourceGroup.json not found: " + str(group_file))
    data = json.loads(group_file.read_text(encoding="utf-8"))
    result = set()
    groups = {}
    for group, value in data.items():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, str):
                continue
            result.add(item)
            groups.setdefault(item, []).append(group)
    return sorted(result), groups


def adapter_type_rows():
    rows = []
    for adapter in ADAPTERS:
        report = adapter.dependency_report()
        caps = report.get("capabilities") or {}
        data_caps = {
            "initSource": bool(caps.get("initSource")),
            "prepareTarget": bool(caps.get("prepareTarget")),
            "fakerCrud": bool(caps.get("fakerCrud")),
            "compare": bool(caps.get("compare")),
        }
        if all(data_caps.values()):
            status = "READY"
        elif any(data_caps.values()):
            status = "PARTIAL"
        else:
            status = "ROUTED_ONLY"
        for ds_type in report.get("dataSourceTypes") or []:
            rows.append(
                {
                    "type": ds_type,
                    "adapter": report.get("adapter"),
                    "dataModel": report.get("dataModel"),
                    "defaultProfile": report.get("defaultProfile"),
                    "status": status,
                    "capabilities": caps,
                    "installCommands": report.get("installCommands") or [],
                }
            )
    return sorted(rows, key=lambda row: row["type"].lower())


def main():
    parser = argparse.ArgumentParser(description="Audit CloudCanal frontend datasource types against autotest adapter routing.")
    parser.add_argument("--frontend-dir", default=os.environ.get("CLOUDCANAL_WEB_DIR", ""), help="Path to clouddm-web checkout.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    if not args.frontend_dir:
        raise SystemExit("ERROR: --frontend-dir or CLOUDCANAL_WEB_DIR is required")
    frontend_dir = Path(args.frontend_dir).expanduser().resolve()
    frontend, groups = frontend_types(frontend_dir)
    adapter_rows = adapter_type_rows()
    registered = sorted({row["type"] for row in adapter_rows})
    row_by_type = {row["type"]: row for row in adapter_rows}
    missing = sorted(set(frontend) - set(registered))
    extra = sorted(set(registered) - set(frontend))
    rows = []
    counts = {"READY": 0, "PARTIAL": 0, "ROUTED_ONLY": 0, "MISSING": 0}
    for ds_type in frontend:
        row = dict(row_by_type.get(ds_type) or {"type": ds_type, "status": "MISSING"})
        row["groups"] = sorted(groups.get(ds_type) or [])
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        rows.append(row)
    summary = {
        "frontendTypes": len(frontend),
        "registeredTypes": len(registered),
        "missingFrontendTypes": missing,
        "extraRegisteredTypes": extra,
        "statusCounts": counts,
    }

    if args.format == "json":
        print(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))
        return

    print("# CloudCanal Datasource Type Coverage")
    print()
    print("- frontendTypes: {frontendTypes}".format(**summary))
    print("- registeredTypes: {registeredTypes}".format(**summary))
    print("- missingFrontendTypes: " + (", ".join(missing) if missing else "none"))
    print("- extraRegisteredTypes: " + (", ".join(extra) if extra else "none"))
    print("- READY: {READY}, PARTIAL: {PARTIAL}, ROUTED_ONLY: {ROUTED_ONLY}, MISSING: {MISSING}".format(**counts))
    print()
    print("| Type | Status | Adapter | Model | Groups |")
    print("| --- | --- | --- | --- | --- |")
    for row in rows:
        print(
            "| {type} | {status} | {adapter} | {model} | {groups} |".format(
                type=row["type"],
                status=row.get("status", ""),
                adapter=row.get("adapter", ""),
                model=row.get("dataModel", ""),
                groups=", ".join(row.get("groups") or []),
            )
        )


if __name__ == "__main__":
    main()
