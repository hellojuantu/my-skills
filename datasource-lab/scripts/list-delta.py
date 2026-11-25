#!/usr/bin/env python3
"""Compare a complete lab snapshot and its published IDs with a finished health report."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def index(rows, label):
    result = {}
    for row in rows:
        key = row["id"]
        if not isinstance(key, (int, str)) or isinstance(key, bool) or key in result:
            raise ValueError(f"{label} contains an invalid or duplicate record ID")
        result[key] = row
    return result


def compare(snapshot, published, report, scope, snapshot_digest, historical):
    complete = index(snapshot, "snapshot")
    previous = index(published, "published list")
    checked = index([row for row in report["records"] if row["scope"] == scope], "report")
    finished = report["summary"]["finishedAt"]
    if not finished or not complete or complete.keys() != checked.keys():
        raise ValueError("a finished report covering each record in this snapshot is required")
    reported_digest = report["summary"].get("snapshotSha256ByScope", {}).get(scope)
    if reported_digest != snapshot_digest and (reported_digest is not None or not historical):
        raise ValueError("the report does not identify the exact source snapshot")
    if not previous.keys() <= complete.keys():
        raise ValueError("published IDs missing from the snapshot require review")
    for key, row in checked.items():
        if not row.get("status") or row["type"] != complete[key]["type"]:
            raise ValueError("a report row has no status or a different datasource type")
    passed = {key for key, row in checked.items() if row["status"] == "pass"}
    return {
        "scope": scope,
        "finishedAt": finished,
        "snapshotVerified": reported_digest == snapshot_digest,
        "total": len(complete),
        "passed": len(passed),
        "add": [key for key in complete if key in passed and key not in previous],
        "remove": [
            {"id": key, "status": checked[key]["status"]}
            for key in previous if key not in passed
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("published", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--scope", default="247", help="report scope matching both input lists")
    parser.add_argument("--historical", action="store_true",
                        help="preview older reports without a snapshot hash; for review only")
    args = parser.parse_args()
    try:
        snapshot = args.snapshot.read_bytes()
        diff = compare(json.loads(snapshot), read_json(args.published), read_json(args.report),
                       args.scope, hashlib.sha256(snapshot).hexdigest(), args.historical)
    except (json.JSONDecodeError, UnicodeError):
        sys.exit("Cannot compare: invalid JSON input.")
    except ValueError as exc:
        sys.exit(f"Cannot compare: {exc}.")
    except (AttributeError, KeyError, TypeError, OSError):
        sys.exit("Cannot compare: use the complete snapshot, its published list and a matching finished report.")
    print(json.dumps(diff, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
