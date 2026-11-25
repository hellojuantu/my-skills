import os
import shutil
import subprocess
import sys
from pathlib import Path

from cc_console.auth import find_sm_crypto_module_dir
from cc_console.client import ApiError, ConsoleClient
from cc_console.clusters import query_default_cluster
from cc_console.utils import print_json


def _read_cookie_no_prompt(args):
    if args.cookie:
        return args.cookie
    if args.cookie_file:
        cookie_path = Path(args.cookie_file).expanduser()
        if cookie_path.exists():
            return cookie_path.read_text(encoding="utf-8").strip()
    return os.environ.get("CC_COOKIE", "").strip()


def _frontend_dir(args):
    values = [
        getattr(args, "frontend_dir", None),
        os.environ.get("CLOUDCANAL_WEB_DIR"),
        os.environ.get("CC_FRONTEND_DIR"),
    ]
    for value in values:
        if value:
            return Path(value).expanduser()

    for start in (Path.cwd(), Path(__file__).resolve()):
        current = start if start.is_dir() else start.parent
        for parent in (current, *current.parents):
            candidates = [parent, parent / "clouddm-web"]
            for candidate in candidates:
                if candidate.name == "clouddm-web" and candidate.exists():
                    return candidate
    return None


def _node_version(node_path):
    if not node_path:
        return None
    try:
        proc = subprocess.run([node_path, "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _check_frontend(frontend_dir):
    if not frontend_dir:
        return {"ok": False, "reason": "CLOUDCANAL_WEB_DIR or --frontend-dir is not set"}
    frontend_dir = frontend_dir.resolve()
    api_dir = frontend_dir / "src" / "services" / "http" / "api"
    required = ["dataJob.js", "datasource.js", "webOp.js", "position.js", "schedule.js", "constant.js"]
    missing = [name for name in required if not (api_dir / name).exists()]
    return {
        "ok": frontend_dir.exists() and not missing,
        "path": str(frontend_dir),
        "missingApiFiles": missing,
    }


def doctor_cmd(args):
    skill_dir = Path(__file__).resolve().parents[2]
    node_path = shutil.which("node")
    cookie = _read_cookie_no_prompt(args)
    base_url = args.base_url or os.environ.get("CC_BASE_URL", "").strip()

    result = {
        "python": {
            "ok": sys.version_info >= (3, 8),
            "version": sys.version.split()[0],
        },
        "skill": {
            "ok": (skill_dir / "SKILL.md").exists() and (skill_dir / "scripts" / "create_datajob.py").exists(),
            "path": str(skill_dir),
        },
        "frontend": _check_frontend(_frontend_dir(args)),
        "node": {
            "ok": bool(node_path),
            "path": node_path,
            "version": _node_version(node_path),
        },
        "smCrypto": {},
        "console": {
            "baseUrlConfigured": bool(base_url),
            "cookieConfigured": bool(cookie),
            "cookieFile": args.cookie_file,
        },
    }

    try:
        result["smCrypto"] = {"ok": True, "nodeModuleDir": find_sm_crypto_module_dir()}
    except ApiError as e:
        result["smCrypto"] = {"ok": False, "reason": str(e)}

    if args.check_api:
        if not base_url or not cookie:
            result["console"]["apiCheck"] = {
                "ok": False,
                "reason": "--check-api requires --base-url/CC_BASE_URL and cookie/CC_COOKIE/--cookie-file",
            }
        else:
            try:
                client = ConsoleClient(base_url, cookie=cookie, timeout=args.timeout, csrf_token=args.csrf_token)
                result["console"]["apiCheck"] = {
                    "ok": True,
                    "defaultCluster": query_default_cluster(client) or {},
                }
            except ApiError as e:
                result["console"]["apiCheck"] = {"ok": False, "reason": str(e)}

    print_json(result)
    return 0
