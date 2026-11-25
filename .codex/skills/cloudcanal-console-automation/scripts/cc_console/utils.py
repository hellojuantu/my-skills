import getpass
import json


SENSITIVE_WORDS = ("password", "passwd", "pwd", "secret", "token", "key", "cookie")


def short_text(text, limit=500):
    text = (text or "").replace("\n", " ").replace("\r", " ")
    if len(text) <= limit:
        return text
    return text[:limit] + "...(truncated,length=" + str(len(text)) + ")"


def parse_int(value, name):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as e:
        raise ValueError(name + " must be an integer") from e
    if parsed <= 0:
        raise ValueError(name + " must be positive")
    return parsed


def parse_kv_overrides(items):
    result = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError("--set expects key=value, got: " + item)
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("--set key can not be empty")
        result[key] = value
    return result


def maybe_read_value_file(value):
    if not value.startswith("@"):
        return value
    path = value[1:]
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def looks_sensitive(name):
    lower = (name or "").lower()
    return any(word in lower for word in SENSITIVE_WORDS)


def prompt_line(label, default=None, required=False, sensitive=False):
    while True:
        suffix = ""
        if default not in (None, ""):
            suffix = " [" + str(default) + "]"
        prompt = label + suffix + ": "
        if sensitive:
            value = getpass.getpass(prompt)
        else:
            value = input(prompt)
        if value == "" and default is not None:
            value = str(default)
        if value != "" or not required:
            return value
        print("  required")


def normalize_bool(value):
    lower = value.strip().lower()
    if lower in ("true", "t", "yes", "y", "1"):
        return "true"
    if lower in ("false", "f", "no", "n", "0"):
        return "false"
    return value


def validate_json_config(config_name, value):
    if value.strip() == "":
        return value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as e:
        raise ValueError(config_name + " expects JSON: " + str(e)) from e
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def mask_value(name, value):
    if value is None:
        return None
    if looks_sensitive(name):
        return "***"
    return value


def mask_payload(value, name=""):
    if isinstance(value, dict):
        return {k: mask_payload(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_payload(v, name) for v in value]
    return mask_value(name, value)


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))
