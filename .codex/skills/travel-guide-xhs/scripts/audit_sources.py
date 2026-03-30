#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = SKILL_DIR / "config" / "source_whitelist.json"
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
URL_RE = re.compile(r"https?://[^\s<>\"]+")


def normalize_host(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in MARKDOWN_LINK_RE.findall(text):
        cleaned = match.rstrip(").,]>")
        if cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
    for match in URL_RE.findall(text):
        cleaned = match.rstrip(").,]>")
        if cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
    return urls


def host_matches_rule(host: str, rule: dict[str, object]) -> bool:
    for domain in rule.get("domains", []):
        domain = normalize_host(str(domain))
        if host == domain or host.endswith(f".{domain}"):
            return True
    for suffix in rule.get("suffixes", []):
        suffix = normalize_host(str(suffix))
        if host == suffix or host.endswith(f".{suffix}"):
            return True
    return False


def build_rules(config: dict[str, object], extra_domains: list[str]) -> list[dict[str, object]]:
    rules = [dict(rule) for rule in config.get("rules", [])]
    for domain in extra_domains:
        host = normalize_host(domain)
        rules.append(
            {
                "name": f"额外官方域名:{host}",
                "tier": "manual_extra_official",
                "domains": [host],
            }
        )
    return rules


def classify_urls(urls: list[str], rules: list[dict[str, object]]) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str]]]:
    approved: dict[str, list[dict[str, str]]] = defaultdict(list)
    unknown: list[dict[str, str]] = []

    for url in urls:
        host = normalize_host(url)
        matched = None
        for rule in rules:
            if host_matches_rule(host, rule):
                matched = rule
                break
        if matched is None:
            unknown.append({"host": host, "url": url})
            continue
        approved[str(matched["tier"])].append(
            {
                "host": host,
                "url": url,
                "rule": str(matched["name"]),
            }
        )
    return approved, unknown


def has_required_domain(urls: list[str], required_domain: str) -> bool:
    required = normalize_host(required_domain)
    for url in urls:
        host = normalize_host(url)
        if host == required or host.endswith(f".{required}"):
            return True
    return False


def summarize(approved: dict[str, list[dict[str, str]]], unknown: list[dict[str, str]], required_domains: list[str], urls: list[str]) -> str:
    lines: list[str] = []
    lines.append("Approved sources by tier:")
    for tier in sorted(approved):
        lines.append(f"- {tier}:")
        host_counts: dict[str, int] = defaultdict(int)
        rules_by_host: dict[str, str] = {}
        for item in approved[tier]:
            host_counts[item["host"]] += 1
            rules_by_host[item["host"]] = item["rule"]
        for host in sorted(host_counts):
            lines.append(f"  - {host} ({host_counts[host]} link(s)) via {rules_by_host[host]}")

    if not approved:
        lines.append("- none")

    if required_domains:
        lines.append("Required domains:")
        for domain in required_domains:
            status = "ok" if has_required_domain(urls, domain) else "missing"
            lines.append(f"- {normalize_host(domain)}: {status}")

    if unknown:
        lines.append("Unknown hosts:")
        by_host: dict[str, list[str]] = defaultdict(list)
        for item in unknown:
            by_host[item["host"]].append(item["url"])
        for host in sorted(by_host):
            lines.append(f"- {host}")
            for url in by_host[host]:
                lines.append(f"  - {url}")
    else:
        lines.append("Unknown hosts: none")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit report URLs against the travel-guide-xhs whitelist."
    )
    parser.add_argument("--input", required=True, help="Markdown or text file to audit.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to the source whitelist JSON.",
    )
    parser.add_argument(
        "--allow-domain",
        action="append",
        default=[],
        help="Add a confirmed official domain to the whitelist for this run.",
    )
    parser.add_argument(
        "--require-domain",
        action="append",
        default=[],
        help="Require at least one URL from the given domain.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()

    text = input_path.read_text(encoding="utf-8")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    urls = extract_urls(text)
    rules = build_rules(config, args.allow_domain)
    approved, unknown = classify_urls(urls, rules)

    missing_required = [
        normalize_host(domain)
        for domain in args.require_domain
        if not has_required_domain(urls, domain)
    ]

    payload = {
        "input": str(input_path),
        "approved": approved,
        "unknown": unknown,
        "required_domains": [normalize_host(domain) for domain in args.require_domain],
        "missing_required_domains": missing_required,
        "recommended_source_tags": config.get("recommended_source_tags", []),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(summarize(approved, unknown, args.require_domain, urls))

    if unknown or missing_required:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
