#!/usr/bin/env python3
"""Check whether a temporary manual deployment is needed on Mini."""

import argparse
from http.client import HTTPException
import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


def image_name(image, *, require_tag=False):
    repository, sep, tag = image.rpartition(":")
    if not sep or "/" in tag:
        if require_tag:
            raise ValueError("--exact-image requires an explicit repository:tag")
        repository, tag = image, "latest"
    if not re.fullmatch(r"[\w][\w.-]{0,127}", tag, re.ASCII):
        raise ValueError("Invalid Docker image tag")
    first, slash, rest = repository.partition("/")
    if slash and ("." in first or ":" in first or first == "localhost"):
        registry, path = first.lower(), rest
    else:
        registry, path = "docker.io", repository
    if not re.fullmatch(r"(?:[a-z0-9.-]+|\[[0-9a-f:]+\])(?::[0-9]+)?", registry):
        raise ValueError("Invalid Docker registry")
    if not all(re.fullmatch(r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*", part) for part in path.split("/")):
        raise ValueError("Invalid Docker image repository")
    if registry in {"index.docker.io", "registry-1.docker.io"}:
        registry = "docker.io"
    if registry == "docker.io" and "/" not in path:
        path = "library/" + path
    return f"{registry}/{path}:{tag}"


def catalog(base_url):
    origin = urlsplit(base_url.rstrip("/"))
    if origin.scheme not in ("http", "https") or not origin.hostname or origin.username is not None:
        raise ValueError("Supply the MotherData HTTP(S) origin without credentials")
    if origin.path or origin.query or origin.fragment:
        raise ValueError("Supply the MotherData origin without a path, query, or fragment")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(origin.geturl() + "/api/ds-types", timeout=10) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("code") != "OK":
        raise ValueError("MotherData template query failed")
    rows = payload.get("data")
    if not isinstance(rows, list) or not rows:
        raise ValueError("MotherData returned an incomplete template catalog")
    for row in rows:
        if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] < 1:
            raise ValueError("MotherData template is missing its ID")
        if not all(isinstance(row.get(key), str) and row[key].strip() for key in ("family", "dockerImage")):
            raise ValueError("MotherData template is missing its family or image")
        image_name(row["dockerImage"])
    return rows


def family_name(value, rows):
    key = re.sub(r"[\s_-]", "", value).lower()
    key = {"saphana": "hana", "oraclexe": "oracle", "oceanbasece": "oceanbase"}.get(key, key)
    families = {row["family"].lower(): row["family"].upper() for row in rows}
    if key in families:
        return families[key]
    # Reuse the engine names and abbreviations already accepted by Console Automation.
    console_scripts = Path(__file__).resolve().parents[2] / "cloudcanal-console-automation" / "scripts"
    sys.path.insert(0, str(console_scripts))
    from cc_console.datasource import DS_TYPE_ALIASES

    canonical = DS_TYPE_ALIASES.get(key)
    if not canonical:
        raise ValueError(f"Unknown engine {value!r}. Supply a MotherData family or CloudCanal engine name")
    return canonical.upper()


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Exit 0: temporary manual route. 1: use MotherData. 2: unable to decide.")
    parser.add_argument("base_url", help="MotherData site origin. Use the host recorded in mini.env.")
    parser.add_argument("family", help="database engine, such as MongoDB, CK or OceanBase")
    parser.add_argument("--exact-image", help="use only when the request requires this exact repository and tag")
    args = parser.parse_args()
    try:
        rows = catalog(args.base_url)
        family = family_name(args.family, rows)
        requested = image_name(args.exact_image, require_tag=True) if args.exact_image else None
        candidates = []
        matches = []
        other_family = None
        for row in sorted(rows, key=lambda item: item["id"]):
            same_image = requested == image_name(row["dockerImage"])
            if row["family"].upper() != family:
                if same_image:
                    other_family = row["family"]
                continue
            candidates.append({"id": row["id"], "image": row["dockerImage"]})
            if not requested or same_image:
                matches.append(row["id"])
        if other_family and not matches:
            raise ValueError(f"Image belongs to MotherData family {other_family}, check the requested engine")
    except (HTTPException, ImportError, OSError, ValueError) as error:
        print(f"Cannot determine deployment route: {error}", file=sys.stderr)
        return 2

    result = {
        "family": family,
        "exactImage": requested,
        "route": "motherdata" if matches else "temporary-manual",
        "matchingTemplateIds": matches,
        "familyTemplates": candidates,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 1 if matches else 0


if __name__ == "__main__":
    sys.exit(main())
