#!/usr/bin/env python3
"""Check MotherData coverage and current Worker results from the Mini Console."""

import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit


DEFAULT_SLOTS = {"8111", "8112"}


def unique_fields(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicate JSON field")
        data[key] = value
    return data


def read_object(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_fields)
    except (OSError, ValueError) as error:
        raise ValueError(f"{path.name}: cannot read a JSON object with unique fields") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a JSON object")
    return data


def timestamp(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name}: supply an ISO 8601 timestamp with a timezone")
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name}: supply an ISO 8601 timestamp with a timezone") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{name}: supply an ISO 8601 timestamp with a timezone")
    return parsed


def motherdata_id(value):
    return isinstance(value, str) and value.isascii() and value.isdecimal() and not value.startswith("0")


def lab_record(value):
    return isinstance(value, str) and bool(value) and not any(ch.isspace() for ch in value) and any(ch.isalpha() for ch in value)


def source_sort(value):
    return (0, int(value)) if motherdata_id(value) else (1, value)


def inventory_ids(inventory, selected=None):
    sources = inventory.get("dataSources")
    if not isinstance(sources, list) or (not sources and selected is None):
        raise ValueError("dataSources: capture the full MotherData inventory with check-service.py")
    ids = [source.get("id") if isinstance(source, dict) else None for source in sources]
    if any(type(value) is not int or value < 1 for value in ids):
        raise ValueError("dataSources: expected positive MotherData IDs")
    if len(set(ids)) != len(ids):
        raise ValueError("dataSources: duplicate MotherData ID")
    available = {str(value) for value in ids}
    if selected is None:
        return available
    if any(not motherdata_id(value) and not lab_record(value) for value in selected):
        raise ValueError("--source-id: supply a positive MotherData ID as shown in the inventory")
    if len(set(selected)) != len(selected):
        raise ValueError("--source-id: duplicate MotherData ID")
    numeric = [value for value in selected if motherdata_id(value)]
    unknown = set(numeric) - available
    if unknown:
        raise ValueError(f"--source-id: IDs absent from MotherData inventory: {', '.join(sorted(unknown, key=source_sort))}")
    return set(numeric) | {value for value in selected if not motherdata_id(value)}


def expected_connections(data, ids, required_slots):
    slots = data.get("slots")
    if not isinstance(slots, dict) or slots.keys() != required_slots:
        required = ", ".join(sorted(required_slots))
        raise ValueError(f"slots: supply evidence for {required}; use --slot for a single-slot rollout")

    connections = {}
    for slot, config in slots.items():
        sources = config.get("sources") if isinstance(config, dict) else None
        if not isinstance(sources, dict):
            raise ValueError(f"slot {slot}: supply its MotherData ID to CloudCanal instanceId mapping")
        cluster = config.get("cluster")
        if not isinstance(cluster, str) or not cluster.strip():
            raise ValueError(f"slot {slot}: supply the expected Worker cluster")
        missing = ids - sources.keys()
        if missing:
            raise ValueError(f"slot {slot}: missing MotherData IDs {', '.join(sorted(missing, key=source_sort))}")
        if sources.keys() - ids:
            raise ValueError(f"slot {slot}: mapping contains MotherData IDs outside the requested coverage")
        for source_id, instance_id in sources.items():
            if not isinstance(instance_id, str) or not instance_id.strip():
                raise ValueError(f"slot {slot}, MotherData ID {source_id}: supply the CloudCanal instanceId")
            key = (slot, instance_id)
            if key in connections:
                raise ValueError(f"slot {slot}, MotherData ID {source_id}: duplicate CloudCanal instanceId in mapping")
            connections[key] = source_id, cluster
    return connections


def mini_names():
    path = Path(__file__).resolve().parents[2] / "cloudcanal-dev-test" / "scripts" / "mini_names.py"
    spec = importlib.util.spec_from_file_location("mini_names", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def page_slot(page, slots, names, configured, kind):
    if not isinstance(page, str) or any(ch <= " " or ch.isspace() for ch in page):
        return None
    try:
        url = urlsplit(page)
        port = url.port
    except ValueError:
        return None
    if url.scheme not in ("http", "https") or url.username is not None or port is None:
        return None
    if url.query:
        return None
    if kind == "api":
        if url.path != "/cloudcanal/console/api/v1/inner/datasource/connection" or url.fragment:
            return None
    elif url.path != "/" or url.fragment != "/ccdatasource":
        return None
    slot = str(port)
    if slot not in slots or not names.host_matches(url.hostname, configured):
        return None
    return slot


def verify_results(data, connections, not_before, slots, names, configured, evidence_kind):
    results = data.get("results")
    if not isinstance(results, list):
        raise ValueError("results: supply the Console Worker connection results")

    latest = datetime.now(timezone.utc) + timedelta(minutes=5)
    seen = set()
    errors = []
    for index, row in enumerate(results, start=1):
        if not isinstance(row, dict):
            errors.append(f"result {index}: expected a result object")
            continue
        field = "requestUrl" if evidence_kind == "api" else "pageUrl"
        page = row.get(field)
        slot = page_slot(page, slots, names, configured, evidence_kind)
        instance_id = row.get("instanceId")
        key = (slot, instance_id)
        if not isinstance(instance_id, str) or key not in connections:
            location = "connection API response" if evidence_kind == "api" else "data-source page"
            errors.append(f"result {index}: expected a mapped instanceId on its declared Mini Console {location}")
            continue

        source_id, expected_cluster = connections[key]
        kind = "MotherData ID" if motherdata_id(source_id) else "labRecord"
        label = f"slot {slot}, {kind} {source_id}"
        if key in seen:
            errors.append(f"{label}: duplicate result")
        seen.add(key)
        if row.get("cluster") != expected_cluster:
            errors.append(f"{label}: Worker cluster differs from expected; check the Console selection")
        if row.get("status") != "Successful":
            errors.append(f"{label}: Worker did not report Successful; run Test Connection in Console")
        try:
            tested_at = timestamp(row.get("testedAt"), label)
            if tested_at < not_before:
                errors.append(f"{label}: result predates this run; rerun Test Connection")
            if tested_at > latest:
                errors.append(f"{label}: result time is in the future; check the evidence timestamp")
        except ValueError as error:
            errors.append(str(error))

    for slot, instance_id in sorted(connections.keys() - seen):
        source_id, _ = connections[slot, instance_id]
        kind = "MotherData ID" if motherdata_id(source_id) else "labRecord"
        errors.append(f"slot {slot}, {kind} {source_id}: missing Worker result")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path, help="full MotherData inventory captured by check-service.py")
    parser.add_argument("expected", type=Path, help="Mini slot mappings and run start")
    parser.add_argument("evidence", type=Path, help="sanitized Console Worker connection results")
    parser.add_argument("--evidence-kind", choices=("api", "browser"), default="api",
                        help="use API requestUrl by default; browser pageUrl only when the user requested pages")
    parser.add_argument("--slot", type=int, metavar="PORT",
                        help="check the registered Mini Console port for a single slot (default: 8111 and 8112)")
    parser.add_argument("--source-id", action="append", metavar="ID",
                        help="check a MotherData ID or Lab record (repeat for each source); default: full MotherData inventory")
    args = parser.parse_args()
    if args.slot is not None and not 1 <= args.slot <= 65535:
        parser.error("--slot must be a TCP port between 1 and 65535")

    try:
        ids = inventory_ids(read_object(args.inventory), args.source_id)
        expected = read_object(args.expected)
        not_before = timestamp(expected.get("notBefore"), "notBefore")
        required_slots = {str(args.slot)} if args.slot is not None else DEFAULT_SLOTS
        connections = expected_connections(expected, ids, required_slots)
        names = mini_names()
        _expected_host, configured = names.console_names()
        if not configured:
            raise ValueError("Fill cloudcanal-dev-test/skills/cc-setup/mini.env before checking Mini Console results.")
        errors = verify_results(read_object(args.evidence), connections, not_before, required_slots, names, configured, args.evidence_kind)
    except ValueError as error:
        errors = [str(error)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print(f"Worker Test Connection Successful for {len(connections)} data-source registrations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
