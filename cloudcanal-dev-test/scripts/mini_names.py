#!/usr/bin/env python3
"""Names for this checkout's Mini, taken from mini.env."""

import os
from pathlib import Path
from urllib.parse import urlsplit


MINI_NAME_KEYS = ("MINI_HOSTNAME", "MINI_TAILSCALE_NAME", "MINI_SSH_HOST")


def mini_env_path():
    return Path(__file__).resolve().parents[1] / "skills" / "cc-setup" / "mini.env"


def read_values(path):
    values = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def normalized_name(host):
    return (host or "").strip().lower().rstrip(".")


def console_names(env_path=None):
    values = read_values(env_path or mini_env_path())
    for key in MINI_NAME_KEYS:
        configured = values.get(key, "")
        forwarded = os.environ.get(f"CC_{key}", "").strip()
        if configured and forwarded and normalized_name(configured) != normalized_name(forwarded):
            raise ValueError(f"CC_{key} does not match mini.env")
        values[key] = configured or forwarded
    return values["MINI_HOSTNAME"], {normalized_name(values[key]) for key in MINI_NAME_KEYS if values[key]}


def host_matches(host, names):
    return normalized_name(host) in names


def split_host_port(url):
    value = (url or "").strip()
    try:
        parts = urlsplit(value if "://" in value else "//" + value)
        return normalized_name(parts.hostname), parts.port
    except ValueError:
        return "", None
