import json
import time
import uuid
from http.cookies import CookieError, SimpleCookie
from urllib.parse import urlencode
from urllib import error, request

from cc_console.utils import short_text


SUCCESS_CODE = "1"


class ApiError(RuntimeError):
    pass


def cookie_value(cookie_header, name):
    if not cookie_header:
        return None
    try:
        jar = SimpleCookie()
        jar.load(cookie_header)
        if name in jar:
            return jar[name].value
    except CookieError:
        pass

    for item in cookie_header.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        if key.strip() == name:
            return value.strip()
    return None


class ConsoleClient:

    def __init__(self, base_url, cookie=None, timeout=30, csrf_token=None, retries=2, extra_headers=None):
        self.base_url = base_url.rstrip("/")
        self.cookie = cookie
        self.timeout = timeout
        self.csrf_token = csrf_token
        self.retries = retries
        self.extra_headers = extra_headers or {}

    def endpoint(self, path):
        return self.base_url + path

    def headers(self, content_type=None):
        result = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self.cookie:
            result["Cookie"] = self.cookie
        token = self.csrf_token or cookie_value(self.cookie, "csrf-token")
        if token:
            result["csrf-token"] = token
        if content_type:
            result["Content-Type"] = content_type
        result.update(self.extra_headers)
        return result

    def post_json(self, path, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.endpoint(path),
            data=body,
            headers=self.headers("application/json; charset=utf-8"),
            method="POST",
        )
        return self.send(req)

    def get_json(self, path, payload=None):
        return self.send(self.build_get_request(path, payload))

    def post_multipart(self, path, fields):
        boundary, body = encode_multipart(fields)
        req = request.Request(
            self.endpoint(path),
            data=body,
            headers=self.headers("multipart/form-data; boundary=" + boundary),
            method="POST",
        )
        return self.send(req)

    def post_json_raw(self, path, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.endpoint(path),
            data=body,
            headers=self.headers("application/json; charset=utf-8"),
            method="POST",
        )
        return self.send_raw(req)

    def get_raw(self, path, payload=None):
        return self.send_raw(self.build_get_request(path, payload))

    def post_multipart_raw(self, path, fields):
        boundary, body = encode_multipart(fields)
        req = request.Request(
            self.endpoint(path),
            data=body,
            headers=self.headers("multipart/form-data; boundary=" + boundary),
            method="POST",
        )
        return self.send_raw(req)

    def build_get_request(self, path, payload=None):
        query = encode_query(payload or {})
        url = self.endpoint(path)
        if query:
            separator = "&" if "?" in url else "?"
            url += separator + query
        return request.Request(url, headers=self.headers(), method="GET")

    def send_raw(self, req):
        attempts = self.retries + 1
        for attempt in range(attempts):
            try:
                with request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read()
                    status = resp.status
                    headers = dict(resp.headers.items())
                break
            except error.HTTPError as e:
                body = e.read()
                text = body.decode("utf-8", errors="replace")
                raise ApiError("HTTP " + str(e.code) + ": " + short_text(text)) from e
            except error.URLError as e:
                if attempt + 1 >= attempts:
                    raise ApiError("request failed: " + str(e.reason)) from e
                time.sleep(0.5 * (attempt + 1))
        return status, headers, body

    def send(self, req):
        status, headers, body = self.send_raw(req)
        text = body.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ApiError("response is not JSON: " + short_text(text)) from e

    def ensure_success(self, response, action):
        code = str(response.get("code", ""))
        if code == SUCCESS_CODE:
            return response.get("data")

        msg = response.get("msg") or "unknown error"
        request_id = response.get("requestId")
        suffix = ""
        if request_id:
            suffix = ", requestId=" + str(request_id)
        raise ApiError(action + " failed, code=" + code + ", msg=" + str(msg) + suffix)


def encode_multipart(fields):
    boundary = "----CloudCanalDatasource" + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        if value is None:
            continue
        content_type = None
        filename = None
        if isinstance(value, MultipartPart):
            content_type = value.content_type
            value = value.value
        if isinstance(value, MultipartFile):
            content_type = value.content_type
            filename = value.filename
            value = value.value
        header = 'Content-Disposition: form-data; name="' + name + '"'
        if filename:
            header += '; filename="' + filename + '"'
        chunks.append(("--" + boundary).encode("utf-8"))
        chunks.append(header.encode("utf-8"))
        if content_type:
            chunks.append(("Content-Type: " + content_type).encode("utf-8"))
        chunks.append(b"")
        chunks.append(value if isinstance(value, bytes) else str(value).encode("utf-8"))
    chunks.append(("--" + boundary + "--").encode("utf-8"))
    chunks.append(b"")
    return boundary, b"\r\n".join(chunks)


def encode_query(payload):
    items = []
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        items.append((key, value))
    return urlencode(items)


class MultipartPart:

    def __init__(self, value, content_type=None):
        self.value = value
        self.content_type = content_type


class MultipartFile:

    def __init__(self, value, filename, content_type="application/octet-stream"):
        self.value = value
        self.filename = filename
        self.content_type = content_type


def json_part(value):
    return MultipartPart(json.dumps(value, ensure_ascii=False), "application/json; charset=utf-8")
