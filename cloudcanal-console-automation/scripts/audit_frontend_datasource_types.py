#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from cc_console.datasource import DS_TYPE_ALIASES


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


def main():
    parser = argparse.ArgumentParser(description="Audit CloudCanal frontend datasource types against CLI type names.")
    parser.add_argument("--frontend-dir", default=os.environ.get("CLOUDCANAL_WEB_DIR", ""), help="Path to clouddm-web checkout.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    if not args.frontend_dir:
        raise SystemExit("ERROR: --frontend-dir or CLOUDCANAL_WEB_DIR is required")
    frontend_dir = Path(args.frontend_dir).expanduser().resolve()
    frontend, groups = frontend_types(frontend_dir)
    registered = set(DS_TYPE_ALIASES.values())
    missing = sorted(set(frontend) - registered)
    extra = sorted(registered - set(frontend))
    counts = {"RECOGNIZED": len(frontend) - len(missing), "MISSING": len(missing)}
    rows = [
        {"type": ds_type, "status": "RECOGNIZED" if ds_type in registered else "MISSING", "groups": sorted(groups[ds_type])}
        for ds_type in frontend
    ]
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
    print("- Recognized by CLI: {RECOGNIZED}, missing: {MISSING}".format(**counts))
    print()
    print("| Type | Status | Groups |")
    print("| --- | --- | --- |")
    for row in rows:
        print(
            "| {type} | {status} | {groups} |".format(
                type=row["type"],
                status=row["status"],
                groups=", ".join(row["groups"]),
            )
        )


if __name__ == "__main__":
    main()
