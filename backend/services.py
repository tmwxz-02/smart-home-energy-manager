"""Application logic on top of SQLite: rooms, devices, settings, readings,
decisions and virtual device control. Knows nothing about HTTP."""

import json

from .config import DEVICE_LIMITS, DEVICE_TYPES, SETTING_RULES
from .db import get_settings, rows, save_settings
from .engine import Engine, model_params, parse_ts
from .priors import PriorCache


class ValidationError(ValueError):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or []


class NotFound(LookupError):
    pass


# ---------------------------------------------------------------- settings

def validate_settings(conn, values):
    if not isinstance(values, dict) or not values:
        raise ValidationError("Send at least one setting to change.")
    current = get_settings(conn)
    clean = {}
    errors = []
    for key, value in values.items():
        rule = SETTING_RULES.get(key)
        if rule is None:
            errors.append(f"Unknown setting '{key}'.")
            continue
        kind, low, high = rule
        if kind == "str":
            if not isinstance(value, str) or not low <= len(value.strip()) <= high:
                errors.append(f"{key} must be text of {low}-{high} characters.")
                continue
            clean[key] = value.strip()
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{key} must be a number.")
            continue
        if kind == "choice":
            if value not in low:
                errors.append(f"{key} must be one of {', '.join(map(str, low))}.")
                continue
            clean[key] = int(value)
            continue
        if kind == "int" and int(value) != value:
            errors.append(f"{key} must be a whole number.")
            continue
        if not low <= value <= high:
            errors.append(f"{key} must be between {low} and {high}.")
            continue
        clean[key] = int(value) if kind == "int" else float(value)
    merged = {**current, **clean}
    if not errors and merged["motion_if_occupied"] <= merged["motion_if_empty"]:
        errors.append("P(motion | occupied) must be greater than P(motion | empty), "
                      "otherwise motion would not be evidence of presence.")
    if ("interval_minutes" in clean and clean["interval_minutes"] != current["interval_minutes"]
            and conn.execute("SELECT 1 FROM readings LIMIT 1").fetchone()):
        errors.append("The interval length cannot change after readings are stored, because "
                      "every stored reading covers one interval of the old length.")
    if errors:
        raise ValidationError("Some settings are invalid.", errors)
    return clean


def update_settings(conn, values):
    clean = validate_settings(conn, values)
    save_settings(conn, clean)
    conn.commit()
    return get_settings(conn)


# ---------------------------------------------------------------- rooms

def list_rooms(conn, include_archived=False):
    query = ("SELECT r.*, (SELECT COUNT(*) FROM devices d WHERE d.room_id = r.id AND d.archived = 0) "
             "AS device_count, (SELECT MAX(ts) FROM readings x WHERE x.room_id = r.id) AS last_reading "
             "FROM rooms r")
    if not include_archived:
        query += " WHERE r.archived = 0"
    return rows(conn.execute(query + " ORDER BY r.archived, r.name COLLATE NOCASE"))


def get_room(conn, room_id):
    row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if row is None:
        raise NotFound(f"Room {room_id} does not exist.")
    return dict(row)


def _room_name(conn, name, room_id=None):
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("Room name is required.")
    name = name.strip()
    if len(name) > 60:
        raise ValidationError("Room name must be at most 60 characters.")
    clash = conn.execute("SELECT id FROM rooms WHERE name = ? COLLATE NOCASE AND id IS NOT ?",
                         (name, room_id)).fetchone()
    if clash:
        raise ValidationError(f"A room called '{name}' already exists.")
    return name


def create_room(conn, body):
    name = _room_name(conn, (body or {}).get("name"))
    cursor = conn.execute("INSERT INTO rooms(name) VALUES (?)", (name,))
    conn.commit()
    return get_room(conn, cursor.lastrowid)


def update_room(conn, room_id, body):
    get_room(conn, room_id)
    name = _room_name(conn, (body or {}).get("name"), room_id)
    conn.execute("UPDATE rooms SET name = ? WHERE id = ?", (name, room_id))
    conn.commit()
    return get_room(conn, room_id)


def set_room_archived(conn, room_id, archived):
    get_room(conn, room_id)
    conn.execute("UPDATE rooms SET archived = ? WHERE id = ?", (int(archived), room_id))
    if archived:
        conn.execute("UPDATE devices SET archived = 1 WHERE room_id = ?", (room_id,))
    conn.commit()
    return get_room(conn, room_id)


# ---------------------------------------------------------------- devices

def _device_row(row):
    device = dict(row)
    device["schedule"] = json.loads(device["schedule"])
    device["virtual"] = True   # no hardware integration exists in this project
    return device


def list_devices(conn, include_archived=False, room_id=None):
    query = "SELECT d.*, r.name AS room_name FROM devices d JOIN rooms r ON r.id = d.room_id WHERE 1=1"
    params = []
    if not include_archived:
        query += " AND d.archived = 0"
    if room_id:
        query += " AND d.room_id = ?"
        params.append(room_id)
    query += " ORDER BY d.archived, r.name COLLATE NOCASE, d.name COLLATE NOCASE"
    return [_device_row(row) for row in conn.execute(query, params)]


def get_device(conn, device_id):
    row = conn.execute("SELECT d.*, r.name AS room_name FROM devices d JOIN rooms r ON r.id = d.room_id "
                       "WHERE d.id = ?", (device_id,)).fetchone()
    if row is None:
        raise NotFound(f"Device {device_id} does not exist.")
    return _device_row(row)


def validate_schedule(schedule):
    if (not isinstance(schedule, list) or len(schedule) != 24
            or not all(value in (0, 1, True, False) for value in schedule)):
        raise ValidationError("Schedule must be a list of 24 hourly values (0 or 1).")
    return [1 if value else 0 for value in schedule]


def _device_fields(conn, body, existing=None):
    if not isinstance(body, dict):
        raise ValidationError("Request body must be an object.")
    merged = {**(existing or {}), **body}
    errors = []
    name = merged.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60:
        errors.append("Device name is required (at most 60 characters).")
    device_type = merged.get("type")
    if device_type not in DEVICE_TYPES:
        errors.append(f"Type must be one of: {', '.join(DEVICE_TYPES)}.")
    room_id = merged.get("room_id")
    room = None
    if isinstance(room_id, bool) or not isinstance(room_id, int):
        errors.append("Choose a room.")
    else:
        room = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        if room is None:
            errors.append("The selected room does not exist.")
        elif room["archived"]:
            errors.append("The selected room is archived. Restore it first.")
    preset = DEVICE_TYPES.get(device_type, DEVICE_TYPES["other"])
    values = {}
    labels = {"power_w": "Rated power (W)", "comfort_value_per_hour": "Comfort value per hour",
              "startup_cost": "Start-up cost"}
    for key, (low, high) in DEVICE_LIMITS.items():
        value = merged.get(key, preset[key])
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{labels[key]} must be a number.")
        elif not low <= value <= high:
            errors.append(f"{labels[key]} must be between {low} and {high}.")
        else:
            values[key] = float(value)
    schedule = merged.get("schedule", [0] * 24)
    try:
        schedule = validate_schedule(schedule)
    except ValidationError as error:
        errors.append(str(error))
    if errors:
        raise ValidationError("The device could not be saved.", errors)
    return {"name": name.strip(), "type": device_type, "room_id": room_id,
            "schedule": json.dumps(schedule), **values}


def create_device(conn, body):
    fields = _device_fields(conn, body)
    cursor = conn.execute(
        "INSERT INTO devices(room_id, name, type, power_w, comfort_value_per_hour, startup_cost, "
        "schedule) VALUES (:room_id, :name, :type, :power_w, :comfort_value_per_hour, "
        ":startup_cost, :schedule)", fields)
    conn.commit()
    return get_device(conn, cursor.lastrowid)


def update_device(conn, device_id, body):
    existing = get_device(conn, device_id)
    allowed = {"name", "type", "room_id", "power_w", "comfort_value_per_hour", "startup_cost",
               "schedule"}
    unknown = set(body or {}) - allowed
    if unknown:
        raise ValidationError(f"Unknown field(s): {', '.join(sorted(unknown))}.")
    fields = _device_fields(conn, body, {key: existing[key] for key in allowed})
    conn.execute(
        "UPDATE devices SET room_id = :room_id, name = :name, type = :type, power_w = :power_w, "
        "comfort_value_per_hour = :comfort_value_per_hour, startup_cost = :startup_cost, "
        "schedule = :schedule WHERE id = :id", {**fields, "id": device_id})
    conn.commit()
    return get_device(conn, device_id)


def set_device_archived(conn, device_id, archived):
    device = get_device(conn, device_id)
    if not archived:
        room = get_room(conn, device["room_id"])
        if room["archived"]:
            raise ValidationError("Restore the room first, then the device.")
    conn.execute("UPDATE devices SET archived = ? WHERE id = ?", (int(archived), device_id))
    conn.commit()
    return get_device(conn, device_id)


def control_device(conn, device_id, body):
    """Virtual control: switch between auto and manual, or set the manual state."""
    device = get_device(conn, device_id)
    if device["archived"]:
        raise ValidationError("Archived devices cannot be controlled.")
    body = body or {}
    mode = body.get("mode", device["mode"])
    state = body.get("state", device["manual_state"])
    if mode not in ("auto", "manual"):
        raise ValidationError("mode must be 'auto' or 'manual'.")
    if state not in ("ON", "OFF"):
        raise ValidationError("state must be 'ON' or 'OFF'.")
    if "state" in body and mode == "auto":
        mode = "manual"   # pressing ON/OFF is a manual override
    conn.execute("UPDATE devices SET mode = ?, manual_state = ? WHERE id = ?",
                 (mode, state, device_id))
    detail = (f"Manual override: virtual device set {state}" if mode == "manual"
              else "Returned to automatic (AI) control")
    conn.execute("INSERT INTO control_log(device_id, action, detail) VALUES (?, ?, ?)",
                 (device_id, state if mode == "manual" else "AUTO", detail))
    conn.commit()
    return get_device(conn, device_id)


def control_log(conn, device_id=None, limit=20):
    query = ("SELECT c.*, d.name AS device_name FROM control_log c JOIN devices d ON d.id = c.device_id")
    params = []
    if device_id:
        query += " WHERE c.device_id = ?"
        params.append(device_id)
    query += " ORDER BY c.id DESC LIMIT ?"
    params.append(limit)
    return rows(conn.execute(query, params))


def current_state(conn, device):
    """The virtual device's present state."""
    if device["mode"] == "manual":
        return device["manual_state"], "manual"
    row = conn.execute("SELECT action, ts FROM decisions WHERE device_id = ? ORDER BY ts DESC LIMIT 1",
                       (device["id"],)).fetchone()
    if row is None:
        return "OFF", "no decisions yet"
    return row["action"], f"AI decision for {row['ts'].replace('T', ' ')}"


# ---------------------------------------------------------------- readings

def check_reading_time(ts, interval_minutes):
    """Validate 'YYYY-MM-DDTHH:MM' aligned to the interval grid. Returns the normalised text."""
    if not isinstance(ts, str):
        raise ValidationError("Time is required.")
    text = ts.strip().replace(" ", "T")
    if len(text) == 19:          # allow seconds if they are zero
        if text[16:] != ":00":
            raise ValidationError(f"Time '{ts}' must not have seconds.")
        text = text[:16]
    try:
        moment = parse_ts(text)
    except ValueError:
        raise ValidationError(f"Time '{ts}' is not in the format YYYY-MM-DD HH:MM.") from None
    if moment.minute % interval_minutes:
        raise ValidationError(f"Time '{ts}' must start an interval: minutes must be a multiple of "
                              f"{interval_minutes}.")
    return text


def active_devices(conn):
    return [d for d in list_devices(conn) if not d["archived"]]


def ingest_readings(conn, items, source, import_id=None):
    """Store readings (already validated) and run the AI for each of them in time order.

    ``items``: list of {room_id, ts, motion, occupied}. Returns (readings, decisions).
    """
    settings = get_settings(conn)
    items = sorted(items, key=lambda item: (item["ts"], item["room_id"]))
    ids = {}
    for item in items:
        cursor = conn.execute(
            "INSERT INTO readings(room_id, ts, motion, occupied, source, import_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (item["room_id"], item["ts"], int(item["motion"]),
             None if item.get("occupied") is None else int(item["occupied"]), source, import_id))
        ids[(item["room_id"], item["ts"])] = cursor.lastrowid

    devices = active_devices(conn)
    engine = Engine(settings, devices, PriorCache(conn, settings).get)
    # Continue the filter and device state from the stored history.
    first_ts = {}
    for item in items:
        first_ts.setdefault(item["room_id"], item["ts"])
    for room_id, ts in first_ts.items():
        row = conn.execute("SELECT ts, predicted FROM readings WHERE room_id = ? AND ts < ? "
                           "AND predicted IS NOT NULL ORDER BY ts DESC LIMIT 1",
                           (room_id, ts)).fetchone()
        if row:
            engine.last_reading[room_id] = (row["ts"], row["predicted"])
    for device in devices:
        ts = first_ts.get(device["room_id"])
        if ts is None:
            continue
        row = conn.execute("SELECT action, baseline_action FROM decisions WHERE device_id = ? "
                           "AND ts < ? ORDER BY ts DESC LIMIT 1", (device["id"], ts)).fetchone()
        if row:
            engine.device_state[device["id"]] = row["action"]
            engine.baseline_state[device["id"]] = row["baseline_action"]

    params = json.dumps(model_params(settings))
    all_decisions = []
    stored = []
    for item in items:
        belief, decisions = engine.process(item)
        reading_id = ids[(item["room_id"], item["ts"])]
        conn.execute("UPDATE readings SET prior = ?, prior_source = ?, posterior = ?, predicted = ? "
                     "WHERE id = ?", (belief["prior"], belief["prior_source"], belief["posterior"],
                                      belief["predicted"], reading_id))
        stored.append({**item, **belief, "id": reading_id})
        for decision in decisions:
            decision["reading_id"] = reading_id
            decision["params"] = params
            conn.execute(
                "INSERT INTO decisions(reading_id, device_id, room_id, ts, interval_minutes, mode, "
                "scheduled, motion, prior, posterior, predicted, previous_state, q_on, q_off, horizon, "
                "action, baseline_action, energy_wh, baseline_energy_wh, starts, baseline_starts, "
                "explanation, params) VALUES (:reading_id, :device_id, :room_id, :ts, "
                ":interval_minutes, :mode, :scheduled, :motion, :prior, :posterior, :predicted, "
                ":previous_state, :q_on, :q_off, :horizon, :action, :baseline_action, :energy_wh, "
                ":baseline_energy_wh, :starts, :baseline_starts, :explanation, :params)", decision)
            all_decisions.append(decision)
    return stored, all_decisions


def add_reading(conn, body):
    """Manual entry of one reading from the UI."""
    if not isinstance(body, dict):
        raise ValidationError("Request body must be an object.")
    settings = get_settings(conn)
    errors = []
    room_id = body.get("room_id")
    room = None
    if isinstance(room_id, bool) or not isinstance(room_id, int):
        errors.append("Choose a room.")
    else:
        room = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        if room is None:
            errors.append("The selected room does not exist.")
        elif room["archived"]:
            errors.append("The selected room is archived.")
    ts = None
    try:
        ts = check_reading_time(body.get("ts"), settings["interval_minutes"])
    except ValidationError as error:
        errors.append(str(error))
    motion = body.get("motion")
    if not isinstance(motion, bool):
        errors.append("Motion must be true or false.")
    occupied = body.get("occupied")
    if occupied is not None and not isinstance(occupied, bool):
        errors.append("Occupied must be true, false or empty (unknown).")
    if not errors and conn.execute("SELECT 1 FROM readings WHERE room_id = ? AND ts = ?",
                                   (room_id, ts)).fetchone():
        errors.append(f"A reading for {room['name']} at {ts.replace('T', ' ')} already exists.")
    if errors:
        raise ValidationError("The reading could not be saved.", errors)
    with conn:
        stored, decisions = ingest_readings(
            conn, [{"room_id": room_id, "ts": ts, "motion": motion, "occupied": occupied}], "manual")
    names = {d["id"]: d["name"] for d in list_devices(conn, include_archived=True)}
    for decision in decisions:
        decision["device_name"] = names.get(decision["device_id"])
    return {"reading": stored[0], "decisions": decisions}


def list_readings(conn, room_id=None, date_from=None, date_to=None, source=None, limit=200, offset=0):
    query = ("SELECT x.*, r.name AS room_name FROM readings x JOIN rooms r ON r.id = x.room_id WHERE 1=1")
    params = []
    query, params = _filters(query, params, "x", room_id, date_from, date_to)
    if source:
        query += " AND x.source = ?"
        params.append(source)
    total = conn.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]
    query += " ORDER BY x.ts DESC, r.name LIMIT ? OFFSET ?"
    return {"items": rows(conn.execute(query, params + [limit, offset])), "total": total}


def list_decisions(conn, room_id=None, device_id=None, date_from=None, date_to=None, action=None,
                   limit=100, offset=0):
    query = ("SELECT c.*, d.name AS device_name, d.type AS device_type, r.name AS room_name, "
             "x.occupied AS occupied FROM decisions c JOIN devices d ON d.id = c.device_id "
             "JOIN rooms r ON r.id = c.room_id JOIN readings x ON x.id = c.reading_id WHERE 1=1")
    params = []
    query, params = _filters(query, params, "c", room_id, date_from, date_to)
    if device_id:
        query += " AND c.device_id = ?"
        params.append(device_id)
    if action in ("ON", "OFF"):
        query += " AND c.action = ?"
        params.append(action)
    total = conn.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]
    query += " ORDER BY c.ts DESC, r.name, d.name LIMIT ? OFFSET ?"
    return {"items": rows(conn.execute(query, params + [limit, offset])), "total": total}


def _filters(query, params, alias, room_id, date_from, date_to):
    if room_id:
        query += f" AND {alias}.room_id = ?"
        params.append(room_id)
    if date_from:
        query += f" AND {alias}.ts >= ?"
        params.append(f"{date_from}T00:00")
    if date_to:
        query += f" AND {alias}.ts <= ?"
        params.append(f"{date_to}T23:59")
    return query, params


# ---------------------------------------------------------------- dashboard

def dashboard(conn):
    devices = list_devices(conn)
    for device in devices:
        device["state"], device["state_source"] = current_state(conn, device)
    rooms = list_rooms(conn)
    totals = conn.execute(
        "SELECT COUNT(DISTINCT reading_id) AS readings, SUM(energy_wh) AS ai_wh, "
        "SUM(baseline_energy_wh) AS base_wh, MIN(ts) AS first_ts, MAX(ts) AS last_ts "
        "FROM decisions").fetchone()
    latest_day = None
    if totals["last_ts"]:
        day = totals["last_ts"][:10]
        latest = conn.execute(
            "SELECT SUM(energy_wh) AS ai_wh, SUM(baseline_energy_wh) AS base_wh FROM decisions "
            "WHERE ts >= ? AND ts <= ?", (f"{day}T00:00", f"{day}T23:59")).fetchone()
        latest_day = {"date": day, "ai_wh": latest["ai_wh"] or 0, "base_wh": latest["base_wh"] or 0}
    recent = list_decisions(conn, limit=6)["items"]
    counts = {
        "rooms": len(rooms), "devices": len(devices),
        "readings": conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0],
        "decisions": conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0],
        "labelled": conn.execute("SELECT COUNT(*) FROM readings WHERE occupied IS NOT NULL").fetchone()[0],
    }
    return {"devices": devices, "rooms": rooms, "counts": counts, "recent_decisions": recent,
            "totals": {"ai_wh": totals["ai_wh"] or 0, "base_wh": totals["base_wh"] or 0,
                       "first_ts": totals["first_ts"], "last_ts": totals["last_ts"]},
            "latest_day": latest_day, "settings": get_settings(conn)}
