"""Tests for the hosting entry point (wsgi.py) and the optional access controls."""

import base64
import io
import json
import os
import shutil
import tempfile
import unittest


def call(method, path, body=None, headers=None, query=""):
    from wsgi import application
    raw = b"" if body is None else json.dumps(body).encode()
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw)}
    for key, value in (headers or {}).items():
        environ["HTTP_" + key.upper().replace("-", "_")] = value
    captured = {}

    def start_response(status, response_headers):
        captured["status"] = int(status.split()[0])
        captured["headers"] = dict(response_headers)

    content = b"".join(application(environ, start_response))
    return captured["status"], captured["headers"], content


class WsgiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="shem-wsgi-")
        self.saved = {key: os.environ.get(key) for key in ("SHEM_DATA_DIR", "SHEM_PASSWORD", "SHEM_READ_ONLY")}
        os.environ["SHEM_DATA_DIR"] = self.folder
        os.environ.pop("SHEM_PASSWORD", None)
        os.environ.pop("SHEM_READ_ONLY", None)

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_static_files_and_traversal(self):
        status, headers, body = call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Smart Home Energy Manager", body)
        status, headers, _ = call("GET", "/js/app.js")
        self.assertTrue(headers["Content-Type"].startswith("text/javascript"))
        self.assertEqual(call("GET", "/../backend/db.py")[0], 404)
        self.assertEqual(call("GET", "/missing.js")[0], 404)

    def test_api_flow_matches_local_server(self):
        status, _, body = call("POST", "/api/rooms", {"name": "Hall"})
        self.assertEqual(status, 201)
        room = json.loads(body)
        status, _, _ = call("POST", "/api/devices", {"name": "Lamp", "type": "light", "room_id": room["id"], "schedule": [1] * 24})
        self.assertEqual(status, 201)
        status, _, body = call("POST", "/api/readings", {"room_id": room["id"], "ts": "2026-11-12T20:00", "motion": False})
        self.assertEqual(status, 201)
        self.assertEqual(len(json.loads(body)["decisions"]), 1)
        status, headers, _ = call("GET", "/api/analytics/report.csv", query="ws=home")
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(call("POST", "/api/rooms", None, query="")[0], 400)   # empty body -> validation error

    def test_read_only_mode(self):
        os.environ["SHEM_READ_ONLY"] = "1"
        status, _, body = call("POST", "/api/rooms", {"name": "Hall"})
        self.assertEqual(status, 403)
        self.assertIn("read-only", json.loads(body)["error"])
        self.assertEqual(call("GET", "/api/rooms")[0], 200)
        status, _, body = call("POST", "/api/explain", {"prior": 0.5, "motion": True})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(call("GET", "/api/meta")[2])["read_only"])

    def test_password(self):
        os.environ["SHEM_PASSWORD"] = "s3cret"
        status, headers, _ = call("GET", "/")
        self.assertEqual(status, 401)
        self.assertIn("Basic", headers["WWW-Authenticate"])
        wrong = "Basic " + base64.b64encode(b"x:nope").decode()
        self.assertEqual(call("GET", "/api/health", headers={"Authorization": wrong})[0], 401)
        right = "Basic " + base64.b64encode(b"anyone:s3cret").decode()
        self.assertEqual(call("GET", "/api/health", headers={"Authorization": right})[0], 200)


if __name__ == "__main__":
    unittest.main()
