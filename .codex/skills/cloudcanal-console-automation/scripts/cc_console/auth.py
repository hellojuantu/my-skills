import os
import json
import re
import subprocess
import tempfile
from pathlib import Path

from cc_console.client import ApiError, ConsoleClient
from cc_console.utils import prompt_line


LOGIN_PATH = "/login"
PUBLIC_KEY_PATH = "/getPublicKey"


def ensure_base_url(args):
    if args.base_url:
        return
    args.base_url = os.environ.get("CC_BASE_URL", "").strip()
    if not args.base_url:
        args.base_url = prompt_line("Console base URL", required=True)


def read_cookie(args):
    origin = args.base_url.rstrip("/").lower()
    slot = re.fullmatch(r"http://mini:([0-9]{1,5})", origin)
    mini = slot is not None and 1 <= int(slot.group(1)) <= 65535
    cookie = args.cookie
    if not cookie and args.cookie_file:
        try:
            with open(args.cookie_file, "r", encoding="utf-8") as f:
                cookie = f.read().strip()
        except FileNotFoundError:
            if not mini:
                raise
    if not cookie:
        cookie = os.environ.get("CC_COOKIE", "").strip()
    if not cookie:
        if mini:
            raise ApiError(
                f"Mini needs an existing session. Ask the user to run create_datajob.py login --base-url {origin} "
                '--save-cookie "$CC_COOKIE_FILE", then pass --cookie-file "$CC_COOKIE_FILE".'
            )
        cookie = prompt_line("Console cookie", required=True, sensitive=True)
    return cookie


def client_from_args(args, need_cookie=True):
    ensure_base_url(args)
    cookie = read_cookie(args) if need_cookie else None
    return ConsoleClient(args.base_url, cookie=cookie, timeout=args.timeout, csrf_token=args.csrf_token, extra_headers=parse_headers(getattr(args, "header", [])))


def parse_headers(items):
    result = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError("--header expects Name=Value, got: " + item)
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("--header name can not be empty")
        result[key] = value
    return result


def find_sm_crypto_module_dir():
    env_dir = os.environ.get("SM_CRYPTO_NODE_MODULE_DIR", "").strip()
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir).expanduser())

    for env_name in ("CLOUDCANAL_WEB_DIR", "CLOUDCANAL_REAKH_DIR", "CC_FRONTEND_DIR", "CC_PROJECT_DIR"):
        value = os.environ.get(env_name, "").strip()
        if value:
            base = Path(value).expanduser()
            candidates.append(base if base.name == "node_modules" else base / "node_modules")

    for start in (Path.cwd(), Path(__file__).resolve()):
        current = start if start.is_dir() else start.parent
        for parent in (current, *current.parents):
            candidates.append(parent / "node_modules")
            candidates.append(parent / "reakh" / "node_modules")
            candidates.append(parent / "clouddm-web" / "node_modules")

    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "sm-crypto").exists():
            return str(candidate)
    raise ApiError(
        "sm-crypto node module not found; set SM_CRYPTO_NODE_MODULE_DIR, "
        "run from a frontend checkout with node_modules, pass --password-encrypted, or use --cookie-file"
    )


def encrypt_password(public_key, password):
    js = r"""
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const { sm2 } = require(input.moduleDir + '/sm-crypto');
process.stdout.write(sm2.doEncrypt(input.password, input.publicKey, 1));
"""
    payload = {
        "moduleDir": find_sm_crypto_module_dir(),
        "publicKey": public_key,
        "password": password,
    }
    try:
        proc = subprocess.run(
            ["node", "-e", js],
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise ApiError("node executable not found; install Node.js, pass --password-encrypted, or use --cookie-file") from e
    if proc.returncode != 0:
        raise ApiError("SM2 encrypt password failed: " + proc.stderr.strip())
    encrypted = proc.stdout.strip()
    if not encrypted:
        raise ApiError("SM2 encrypt password failed: empty result")
    return encrypted


def fetch_public_key(client):
    response = client.post_json(PUBLIC_KEY_PATH, {})
    public_key = client.ensure_success(response, "get public key")
    if not public_key:
        raise ApiError("public key is empty")
    return public_key


def login(base_url, account, password, account_type="PRIMARY_ACCOUNT", login_type="PASSWORD", timeout=30, csrf_token=None, password_encrypted=False):
    client = ConsoleClient(base_url, timeout=timeout, csrf_token=csrf_token)
    encrypted_password = password if password_encrypted else encrypt_password(fetch_public_key(client), password)
    payload = {
        "accountType": account_type,
        "loginType": login_type,
        "account": account,
        "password": encrypted_password,
    }
    response = client.post_json(LOGIN_PATH, payload)
    data = client.ensure_success(response, "login")
    if not data or not data.get("success"):
        raise ApiError("login failed")
    if data.get("needMore"):
        raise ApiError("Login requires more account information. Stop and ask the user to complete it in the Console.")
    if data.get("needMfa"):
        raise ApiError("Login requires MFA. Stop and ask the user to complete it in the Console.")
    token = data.get("token")
    if not token:
        raise ApiError("login succeeded but token is empty")
    return data, "jwt_token=" + token


def login_cmd(args):
    ensure_base_url(args)
    account = args.account or os.environ.get("CC_ACCOUNT", "").strip()
    if not account:
        account = prompt_line("Console account", required=True)
    password = args.password
    if password is None:
        password = os.environ.get("CC_PASSWORD")
    if password is None:
        password = prompt_line("Console password", required=True, sensitive=True)
    data, cookie = login(args.base_url, account, password, args.account_type, args.login_type, args.timeout, args.csrf_token, args.password_encrypted)
    if args.save_cookie:
        destination = Path(args.save_cookie).resolve()
        if destination.exists() and not destination.is_file():
            raise ApiError("--save-cookie requires a regular file")
        with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
            session_file = Path(directory) / "session"
            with session_file.open("w", encoding="utf-8") as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(cookie + "\n")
            session_file.replace(destination)
        print("Login ok, cookie saved to " + args.save_cookie)
    if args.print_cookie or not args.save_cookie:
        print(cookie)
    else:
        print("Login ok, uid=" + str(data.get("uid")))
    return 0
