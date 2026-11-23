"""API layer: routes, request validation and JSON responses.

This module knows nothing about sockets. ``dispatch`` takes the method, the
path, the query parameters, the decoded JSON body and the workspace name and
returns (status, payload) - or (status, payload, content_type, filename) for
file downloads - so it is easy to test.

The workspace ("home" or "demo") comes from the X-Workspace header or the
``ws`` query parameter. Each workspace is a separate SQLite file.
"""

import re
from pathlib import Path

from . import access, analytics, brief, demo, optimizer, services
from .config import APP_NAME, DEVICE_TYPES
from .db import WORKSPACES, WRITE_LOCK, connect, get_settings
from .importer import import_csv
from .priors import hourly_priors
from .services import NotFound, ValidationError

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


class Request:
    def __init__(self, method, path, query=None, body=None, workspace="home"):
        self.method = method
        self.path = path
        self.query = query or {}
        self.body = body
        self.workspace = workspace

    def text(self, name):
        value = self.query.get(name)
        return value.strip() if isinstance(value, str) and value.strip() else None

    def integer(self, name, default=None, low=0, high=10**9):
        value = self.text(name)
        if value is None:
            return default
        try:
            number = int(value)
        except ValueError:
            raise ValidationError(f"Query parameter '{name}' must be a whole number.") from None
        if not low <= number <= high:
            raise ValidationError(f"Query parameter '{name}' must be between {low} and {high}.")
        return number

    def number(self, name):
        value = self.text(name)
        if value is None:
            return None
        try:
            number = float(value)
        except ValueError:
            raise ValidationError(f"Query parameter '{name}' must be a number.") from None
        if number < 0:
            raise ValidationError(f"Query parameter '{name}' must not be negative.")
        return number

    def flag(self, name):
        return self.text(name) in ("1", "true", "yes")

    def filters(self):
        return {"date_from": self.text("from"), "date_to": self.text("to"),
                "room_id": self.integer("room"), "device_id": self.integer("device"),
                "tariff": self.number("tariff")}


# ---------------------------------------------------------------- handlers

def health(conn, req):
    return 200, {"status": "ok"}


def meta(conn, req):
    info = {"app": APP_NAME, "workspace": req.workspace, "device_types": DEVICE_TYPES,
            "settings": get_settings(conn), "demo": None, "read_only": access.read_only()}
    if req.workspace == "demo":
        info["demo"] = demo.demo_meta(conn)
    return 200, info


def settings_get(conn, req):
    return 200, get_settings(conn)


def settings_put(conn, req):
    return 200, services.update_settings(conn, req.body)


def rooms_list(conn, req):
    return 200, services.list_rooms(conn, req.flag("archived"))


def rooms_create(conn, req):
    return 201, services.create_room(conn, req.body)


def rooms_update(conn, req, room_id):
    return 200, services.update_room(conn, room_id, req.body)


def rooms_archive(conn, req, room_id):
    return 200, services.set_room_archived(conn, room_id, True)


def rooms_restore(conn, req, room_id):
    return 200, services.set_room_archived(conn, room_id, False)


def devices_list(conn, req):
    devices = services.list_devices(conn, req.flag("archived"), req.integer("room"))
    for device in devices:
        device["state"], device["state_source"] = services.current_state(conn, device)
    return 200, devices


def devices_create(conn, req):
    return 201, services.create_device(conn, req.body)


def devices_get(conn, req, device_id):
    device = services.get_device(conn, device_id)
    device["state"], device["state_source"] = services.current_state(conn, device)
    device["control_log"] = services.control_log(conn, device_id)
    return 200, device


def devices_update(conn, req, device_id):
    return 200, services.update_device(conn, device_id, req.body)


def devices_archive(conn, req, device_id):
    return 200, services.set_device_archived(conn, device_id, True)


def devices_restore(conn, req, device_id):
    return 200, services.set_device_archived(conn, device_id, False)


def devices_control(conn, req, device_id):
    device = services.control_device(conn, device_id, req.body)
    device["state"], device["state_source"] = services.current_state(conn, device)
    return 200, device


def devices_schedule(conn, req, device_id):
    return 200, optimizer.apply_schedule(conn, device_id, req.body)


def readings_list(conn, req):
    return 200, services.list_readings(
        conn, req.integer("room"), req.text("from"), req.text("to"), req.text("source"),
        req.integer("limit", 200, 1, 1000), req.integer("offset", 0))


def readings_create(conn, req):
    return 201, services.add_reading(conn, req.body)


def readings_import(conn, req):
    body = req.body if isinstance(req.body, dict) else {}
    return 201, import_csv(conn, body.get("filename"), body.get("content"))


def readings_sample(conn, req):
    name = "readings_with_errors.csv" if req.flag("errors") else "readings_example.csv"
    text = (SAMPLES_DIR / name).read_text(encoding="utf-8")
    return 200, text, "text/csv; charset=utf-8", name


def decisions_list(conn, req):
    return 200, services.list_decisions(
        conn, req.integer("room"), req.integer("device"), req.text("from"), req.text("to"),
        req.text("action"), req.integer("limit", 100, 1, 1000), req.integer("offset", 0))


def priors_get(conn, req):
    room_id = req.integer("room")
    if not room_id:
        raise ValidationError("Query parameter 'room' is required.")
    services.get_room(conn, room_id)
    return 200, hourly_priors(conn, room_id, get_settings(conn))


def optimize(conn, req):
    return 200, optimizer.optimise(conn, req.body)


def explain(conn, req):
    return 200, optimizer.explain(conn, req.body)


def brief_run(conn, req):
    """Topic 12 exactly as the course brief states it (toy inputs, no database)."""
    try:
        options = brief.validate_request(req.body if req.method == "POST" else None)
    except ValueError as error:
        raise ValidationError(str(error)) from None
    return 200, brief.run(**options)


def analytics_summary(conn, req):
    return 200, analytics.summary(conn, **req.filters())


def analytics_report(conn, req):
    filters = req.filters()
    text = analytics.report_csv(conn, **filters)
    stamp = f"{filters['date_from'] or 'all'}_{filters['date_to'] or 'all'}"
    return 200, text, "text/csv; charset=utf-8", f"energy_report_{req.workspace}_{stamp}.csv"


def analytics_compare(conn, req):
    return 200, analytics.compare_strategies(conn, **req.filters())


def dashboard(conn, req):
    return 200, services.dashboard(conn)


def control_log(conn, req):
    return 200, services.control_log(conn, req.integer("device"), req.integer("limit", 20, 1, 200))


def demo_reset(req):
    """Regenerate the demo workspace. Runs without an open connection."""
    if req.workspace != "demo":
        raise ValidationError("Demo data can only be generated in the demo workspace.")
    body = req.body if isinstance(req.body, dict) else {}
    kwargs = {key: body[key] for key in ("days", "seed", "start_date") if key in body}
    return 200, demo.generate_demo(**kwargs)


def ensure_demo():
    """Generate the demo workspace with default seed on first use."""
    with WRITE_LOCK:
        conn = connect("demo")
        try:
            exists = demo.demo_meta(conn) is not None
        finally:
            conn.close()
        if not exists:
            demo.generate_demo()


ID = r"(\d+)"
ROUTES = [
    ("GET", r"/api/health", health),
    ("GET", r"/api/meta", meta),
    ("GET", r"/api/dashboard", dashboard),
    ("GET", r"/api/settings", settings_get),
    ("PUT", r"/api/settings", settings_put),
    ("GET", r"/api/rooms", rooms_list),
    ("POST", r"/api/rooms", rooms_create),
    ("PUT", rf"/api/rooms/{ID}", rooms_update),
    ("POST", rf"/api/rooms/{ID}/archive", rooms_archive),
    ("POST", rf"/api/rooms/{ID}/restore", rooms_restore),
    ("GET", r"/api/devices", devices_list),
    ("POST", r"/api/devices", devices_create),
    ("GET", rf"/api/devices/{ID}", devices_get),
    ("PUT", rf"/api/devices/{ID}", devices_update),
    ("POST", rf"/api/devices/{ID}/archive", devices_archive),
    ("POST", rf"/api/devices/{ID}/restore", devices_restore),
    ("POST", rf"/api/devices/{ID}/control", devices_control),
    ("PUT", rf"/api/devices/{ID}/schedule", devices_schedule),
    ("GET", r"/api/control-log", control_log),
    ("GET", r"/api/readings", readings_list),
    ("POST", r"/api/readings", readings_create),
    ("POST", r"/api/readings/import", readings_import),
    ("GET", r"/api/readings/sample\.csv", readings_sample),
    ("GET", r"/api/decisions", decisions_list),
    ("GET", r"/api/priors", priors_get),
    ("POST", r"/api/optimize", optimize),
    ("POST", r"/api/explain", explain),
    ("GET", r"/api/brief", brief_run),
    ("POST", r"/api/brief", brief_run),
    ("GET", r"/api/analytics", analytics_summary),
    ("GET", r"/api/analytics/report\.csv", analytics_report),
    ("GET", r"/api/analytics/compare", analytics_compare),
]
COMPILED = [(method, re.compile(pattern + r"/?$"), handler) for method, pattern, handler in ROUTES]


def dispatch(method, path, query=None, body=None, workspace="home"):
    workspace = workspace or "home"
    if workspace not in WORKSPACES:
        return 400, {"error": f"Unknown workspace '{workspace}'. Use 'home' or 'demo'."}
    req = Request(method, path, query, body, workspace)
    try:
        if method == "POST" and re.fullmatch(r"/api/demo/reset/?", path):
            with WRITE_LOCK:
                return demo_reset(req)
        if workspace == "demo":
            ensure_demo()
        path_known = False
        for route_method, pattern, handler in COMPILED:
            match = pattern.match(path)
            if not match:
                continue
            path_known = True
            if route_method != method:
                continue
            args = [int(group) for group in match.groups()]
            with WRITE_LOCK:
                conn = connect(workspace)
                try:
                    return handler(conn, req, *args)
                finally:
                    conn.close()
        if path_known:
            return 405, {"error": f"Method {method} is not allowed for {path}."}
        return 404, {"error": f"Unknown API path {path}."}
    except ValidationError as error:
        return 400, {"error": str(error), "details": error.details}
    except NotFound as error:
        return 404, {"error": str(error)}
