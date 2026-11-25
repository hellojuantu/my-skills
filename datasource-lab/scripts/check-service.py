#!/usr/bin/env python3
"""Read MotherData health and print a small inventory for before/after comparison."""

import argparse
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit


RECORDS = (
    ("/api/nodes", "nodes", ("id",)),
    ("/api/database-install-runs", "installations", ("id", "status", "dataSourceId")),
    ("/api/data-sources", "dataSources", ("id",)),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="MotherData site origin. Use the host recorded in mini.env.")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    origin = urlsplit(base_url)
    if origin.scheme not in ("http", "https") or not origin.hostname:
        parser.error("base_url must be an HTTP or HTTPS origin")
    if origin.username or origin.password or origin.path or origin.query or origin.fragment:
        parser.error("base_url must be an origin without credentials, path, query or fragment")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get_payload(path):
        try:
            with opener.open(base_url + path, timeout=10) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"{path} returned HTTP {exc.code}") from None
        except (OSError, ValueError):
            raise SystemExit(f"Could not read JSON from {path}") from None
        if not isinstance(payload, dict):
            raise SystemExit(f"Unexpected JSON envelope from {path}")
        return payload

    if get_payload("/actuator/health").get("status") != "UP":
        raise SystemExit("MotherData health is not UP")

    inventory = {}
    for path, category, fields in RECORDS:
        payload = get_payload(path)
        rows = payload.get("data")
        if payload.get("code") != "OK" or not isinstance(rows, list):
            raise SystemExit(f"Record query failed for {category}")
        if any(not isinstance(row, dict) or row.get("id") is None for row in rows):
            raise SystemExit(f"Unexpected record shape for {category}")
        ids = [str(row["id"]) for row in rows]
        if len(set(ids)) != len(ids):
            raise SystemExit(f"Duplicate record ID for {category}")
        if category == "installations":
            for row in rows:
                status = row.get("status")
                if not isinstance(status, str) or not status.strip():
                    raise SystemExit(f"Missing or invalid status for installation {row['id']}")
        inventory[category] = sorted(
            ({field: row.get(field) for field in fields} for row in rows),
            key=lambda row: str(row["id"]),
        )
    print(json.dumps(inventory, indent=2))


if __name__ == "__main__":
    main()
