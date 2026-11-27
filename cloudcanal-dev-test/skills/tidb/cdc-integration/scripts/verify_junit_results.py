#!/usr/bin/env python3
"""Fail unless the ds-tidb JUnit run is complete, green, and has zero skips."""

import argparse
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


REQUIRED_TESTS = {
    (
        "com.clougence.cloudcanal.tidb.TiDBDsFactoryTest",
        "shouldCreateConfiguredTiDBDataSource",
    ),
    (
        "com.clougence.cloudcanal.tidb.worker.reader.incre_new.TestTiInstance",
        "shouldDecodeAllPhysicalTypesIdenticallyFromRealRowV1AndV2Cdc",
    ),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Verify a complete ds-tidb JUnit XML result directory"
    )
    parser.add_argument("results_dir", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    files = sorted(args.results_dir.glob("TEST-*.xml"))
    if not files:
        raise SystemExit(f"No TEST-*.xml files found in {args.results_dir}")

    totals = {name: 0 for name in ("tests", "failures", "errors", "skipped")}
    observed = set()
    skipped_required = set()
    for path in files:
        suite = ET.parse(path).getroot()
        for name in totals:
            totals[name] += int(suite.attrib.get(name, 0))
        for case in suite.iter("testcase"):
            identity = (case.attrib.get("classname", ""), case.attrib.get("name", ""))
            observed.add(identity)
            if identity in REQUIRED_TESTS and case.find("skipped") is not None:
                skipped_required.add(identity)

    missing = REQUIRED_TESTS - observed
    print(
        "JUnit totals: "
        + ", ".join(f"{name}={totals[name]}" for name in totals)
    )
    if missing:
        print("Missing required real tests:", sorted(missing), file=sys.stderr)
    if skipped_required:
        print("Skipped required real tests:", sorted(skipped_required), file=sys.stderr)

    failed = (
        totals["failures"] > 0
        or totals["errors"] > 0
        or totals["skipped"] > 0
        or bool(missing)
        or bool(skipped_required)
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
