"""HTTP layer: serves the frontend files and forwards /api/ requests to api.py.

Uses only the Python standard library, so nothing has to be installed.
"""

import json
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import access, api

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
MAX_BODY_BYTES = 5 * 1024 * 1024


class Handler(SimpleHTTPRequestHandler):
    # Fixed content types. On some Windows PCs the registry maps .js to
    # text/plain, and browsers then refuse to run JavaScript modules.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".svg": "image/svg+xml",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def end_headers(self):
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_body(self, status, body, content_type, filename=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, payload):
        self.send_body(status, json.dumps(payload).encode("utf-8"), "application/json")

    def check_password(self):
        if access.authorised(self.headers.get("Authorization")):
            return True
        body = b"Password required"
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Smart Home Energy Manager", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def handle_api(self, method):
        if not self.check_password():
            return
        parts = urlsplit(self.path)
        if access.blocked_by_read_only(method, parts.path):
            self.send_json(403, {"error": access.READ_ONLY_MESSAGE})
            return
        query = {key: values[-1] for key, values in parse_qs(parts.query).items()}
        workspace = self.headers.get("X-Workspace") or query.get("ws") or "home"
        body = None
        if method in ("POST", "PUT"):
            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                length = 0
            if length > MAX_BODY_BYTES:
                self.send_json(413, {"error": "Request is too large (limit 5 MB)."})
                return
            try:
                raw = self.rfile.read(length) if length else b""
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, UnicodeDecodeError):
                self.send_json(400, {"error": "Request body is not valid JSON."})
                return
        try:
            result = api.dispatch(method, parts.path, query, body, workspace)
        except Exception as error:  # pragma: no cover - safety net
            traceback.print_exc()
            self.send_json(500, {"error": f"Internal error: {error}"})
            return
        if len(result) == 4:
            status, text, content_type, filename = result
            self.send_body(status, text.encode("utf-8"), content_type, filename)
        else:
            self.send_json(*result)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.handle_api("GET")
        elif self.check_password():
            super().do_GET()

    def do_POST(self):
        self.handle_api("POST")

    def do_PUT(self):
        self.handle_api("PUT")

    def log_request(self, code="-", size="-"):
        # Keep the console quiet: only log failed requests.
        if str(getattr(code, "value", code)).startswith(("4", "5")):
            super().log_request(code, size)


class Server(ThreadingHTTPServer):
    # On Windows, address reuse lets a second copy of the server bind the
    # same port silently. Turning it off makes a second start fail clearly.
    allow_reuse_address = False
    daemon_threads = True


def make_server(host="127.0.0.1", port=8000):
    return Server((host, port), Handler)
