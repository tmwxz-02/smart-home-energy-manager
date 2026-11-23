"""Tests for the HTTP server and the JSON API (real sockets, temporary data folder)."""

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp(prefix="shem-http-")
        cls.old = os.environ.get("SHEM_DATA_DIR")
        os.environ["SHEM_DATA_DIR"] = cls.folder
        from backend.server import make_server
        cls.server = make_server("127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        if cls.old is None:
            os.environ.pop("SHEM_DATA_DIR", None)
        else:
            os.environ["SHEM_DATA_DIR"] = cls.old
        shutil.rmtree(cls.folder, ignore_errors=True)

    def call(self, method, path, body=None, workspace="home", raw=None):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json", "X-Workspace": workspace})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def json(self, *args, **kwargs):
        status, _, body = self.call(*args, **kwargs)
        return status, json.loads(body)

    def test_page_and_assets_are_served(self):
        status, headers, body = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Smart Home Energy Manager", body)
        for path, kind in (("/js/app.js", "text/javascript"), ("/css/styles.css", "text/css")):
            _, headers, _ = self.call("GET", path)
            self.assertTrue(headers["Content-Type"].startswith(kind), path)

    def test_health_and_errors(self):
        self.assertEqual(self.json("GET", "/api/health"), (200, {"status": "ok"}))
        self.assertEqual(self.json("GET", "/api/nothing")[0], 404)
        self.assertEqual(self.json("PUT", "/api/health", {})[0], 405)
        self.assertEqual(self.json("POST", "/api/rooms", raw=b"{not json")[0], 400)
        status, data = self.json("GET", "/api/meta", workspace="garage")
        self.assertEqual(status, 400)
        self.assertIn("Unknown workspace", data["error"])

    def test_room_device_reading_flow_over_http(self):
        status, room = self.json("POST", "/api/rooms", {"name": "Office"})
        self.assertEqual(status, 201)
        status, data = self.json("POST", "/api/devices", {"name": "Fan", "type": "fan", "room_id": room["id"], "schedule": [1] * 24})
        self.assertEqual(status, 201)
        status, data = self.json("POST", "/api/readings", {"room_id": room["id"], "ts": "2026-11-12T09:00", "motion": True, "occupied": None})
        self.assertEqual(status, 201)
        self.assertEqual(len(data["decisions"]), 1)
        status, data = self.json("POST", "/api/devices", {"name": "", "type": "toaster", "room_id": room["id"]})
        self.assertEqual(status, 400)
        self.assertGreaterEqual(len(data["details"]), 2)
        status, decisions = self.json("GET", f"/api/decisions?room={room['id']}")
        self.assertEqual(decisions["total"], 1)
        status, summary = self.json("GET", "/api/analytics?from=2026-11-12&to=2026-11-12&tariff=10")
        self.assertEqual(summary["tariff"], 10.0)
        self.assertEqual(self.json("GET", "/api/analytics?tariff=abc")[0], 400)

    def test_csv_download_and_import(self):
        status, headers, body = self.call("GET", "/api/readings/sample.csv")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertTrue(body.startswith(b"timestamp,room,motion,occupied"))
        status, data = self.json("POST", "/api/readings/import", {"filename": "x.csv", "content": body.decode()})
        self.assertEqual(status, 400)                       # rooms do not exist yet
        self.assertIn("does not exist", data["details"][0])
        status, headers, body = self.call("GET", "/api/analytics/report.csv?ws=home")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])

    def test_workspaces_are_separate(self):
        self.json("POST", "/api/rooms", {"name": "Only at home"})
        status, demo_rooms = self.json("GET", "/api/rooms", workspace="demo")   # auto-generated demo
        self.assertEqual(status, 200)
        self.assertNotIn("Only at home", [r["name"] for r in demo_rooms])
        self.assertIn("Living room", [r["name"] for r in demo_rooms])
        status, meta = self.json("GET", "/api/meta", workspace="demo")
        self.assertEqual(meta["demo"]["seed"], 42)
        self.assertEqual(self.json("POST", "/api/demo/reset", {"days": 1}, workspace="home")[0], 400)


if __name__ == "__main__":
    unittest.main()
