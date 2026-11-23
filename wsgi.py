"""WSGI entry point, for hosting the app on a web server (e.g. PythonAnywhere).

Local use does not need this file: ``python app.py`` runs its own server.
A hosting service imports ``application`` from here. It serves the same
frontend files and the same API (backend/api.py) as app.py.

Environment variables (optional):
    SHEM_DATA_DIR   folder for the SQLite files (default: ./data)
    SHEM_PASSWORD   require this password (HTTP Basic auth)
    SHEM_READ_ONLY  1 = visitors cannot change data
"""

import json
import mimetypes
import traceback
from pathlib import Path
from urllib.parse import parse_qs

from backend import access, api

FRONTEND_DIR = (Path(__file__).resolve().parent / "frontend").resolve()
MAX_BODY_BYTES = 5 * 1024 * 1024
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
REASONS = {200: "OK", 201: "Created", 400: "Bad Request", 401: "Unauthorized",
           403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
           413: "Payload Too Large", 500: "Internal Server Error"}


def _respond(start_response, status, body, content_type, extra=None):
    headers = [("Content-Type", content_type), ("Content-Length", str(len(body))),
               ("Cache-Control", "no-store")]
    headers.extend(extra or [])
    start_response(f"{status} {REASONS.get(status, 'OK')}", headers)
    return [body]


def _json(start_response, status, payload, extra=None):
    return _respond(start_response, status, json.dumps(payload).encode("utf-8"),
                    "application/json", extra)


def _static(start_response, path, method):
    if method not in ("GET", "HEAD"):
        return _json(start_response, 405, {"error": "Method not allowed."})
    relative = "index.html" if path in ("", "/") else path.lstrip("/")
    target = (FRONTEND_DIR / relative).resolve()
    if FRONTEND_DIR not in target.parents and target != FRONTEND_DIR:
        return _respond(start_response, 404, b"Not found", "text/plain")
    if target.is_dir():
        target = target / "index.html"
    if not target.is_file():
        return _respond(start_response, 404, b"Not found", "text/plain")
    body = target.read_bytes()
    content_type = TYPES.get(target.suffix) or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    response = _respond(start_response, 200, body, content_type, [("Cache-Control", "no-cache")])
    return [b""] if method == "HEAD" else response


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO") or "/"

    if not access.authorised(environ.get("HTTP_AUTHORIZATION")):
        return _respond(start_response, 401, b"Password required", "text/plain; charset=utf-8",
                        [("WWW-Authenticate", 'Basic realm="Smart Home Energy Manager", charset="UTF-8"')])

    if not path.startswith("/api/"):
        return _static(start_response, path, method)

    if access.blocked_by_read_only(method, path):
        return _json(start_response, 403, {"error": access.READ_ONLY_MESSAGE})

    query = {key: values[-1] for key, values in parse_qs(environ.get("QUERY_STRING", "")).items()}
    workspace = environ.get("HTTP_X_WORKSPACE") or query.get("ws") or "home"
    body = None
    if method in ("POST", "PUT"):
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY_BYTES:
            return _json(start_response, 413, {"error": "Request is too large (limit 5 MB)."})
        raw = environ["wsgi.input"].read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            return _json(start_response, 400, {"error": "Request body is not valid JSON."})
    try:
        result = api.dispatch(method, path, query, body, workspace)
    except Exception as error:  # pragma: no cover - safety net
        traceback.print_exc()
        return _json(start_response, 500, {"error": f"Internal error: {error}"})
    if len(result) == 4:
        status, text, content_type, filename = result
        return _respond(start_response, status, text.encode("utf-8"), content_type,
                        [("Content-Disposition", f'attachment; filename="{filename}"')])
    status, payload = result
    return _json(start_response, status, payload)


if __name__ == "__main__":
    # Quick local check of the WSGI version: python wsgi.py  ->  http://127.0.0.1:8080/
    from wsgiref.simple_server import make_server
    print("WSGI test server on http://127.0.0.1:8080/ (Ctrl+C to stop)")
    make_server("127.0.0.1", 8080, application).serve_forever()
