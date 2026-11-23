"""Demo workspace: reproducible SYNTHETIC data for several days.

Everything generated here is invented. It lives only in data/demo.db and the
UI marks the demo workspace with a banner, so it can never be confused with
the user's own observations.

Generation (same seed -> identical data):
* each room has an assumed hour-of-day occupancy pattern (weekday/weekend);
* true occupancy is a persistent random process: with probability 0.75 the
  room keeps its previous state, otherwise it is redrawn from the pattern;
* the motion sensor fires with P(motion | occupied) and P(motion | empty)
  taken from the current settings (so the controller's sensor model is
  exactly right here - real sensors will not be this convenient);
* the true occupancy is stored as the occupancy label, used ONLY to evaluate
  comfort and the oracle strategy.
"""

import json
import random
from datetime import datetime, timedelta

from .config import DEMO_DEFAULT_DAYS, DEMO_DEFAULT_SEED, DEMO_START_DATE
from .db import connect, get_settings, reset_workspace, save_settings
from .engine import format_ts
from .services import ValidationError, ingest_readings


def _hours(*ranges):
    hours = set()
    for start, end in ranges:
        hours.update(range(start, end))
    return [1 if h in hours else 0 for h in range(24)]


def _pattern(base, spans):
    values = [base] * 24
    for (start, end), value in spans:
        for hour in range(start, end):
            values[hour] = value
    return values


ROOMS = [
    {
        "name": "Living room",
        "weekday": _pattern(0.05, [((7, 9), 0.5), ((12, 14), 0.2), ((17, 18), 0.6), ((18, 23), 0.85)]),
        "weekend": _pattern(0.05, [((9, 12), 0.6), ((12, 23), 0.75)]),
        "devices": [
            {"name": "TV", "type": "tv", "power_w": 110, "schedule": _hours((17, 24))},
            {"name": "Floor lamp", "type": "light", "power_w": 60, "schedule": _hours((16, 24))},
            {"name": "Air conditioner", "type": "ac", "power_w": 1200, "schedule": _hours((12, 23))},
        ],
    },
    {
        "name": "Bedroom",
        "weekday": _pattern(0.05, [((0, 6), 0.95), ((6, 7), 0.8), ((7, 8), 0.4), ((21, 22), 0.4),
                                   ((22, 24), 0.85)]),
        "weekend": _pattern(0.05, [((0, 9), 0.95), ((9, 10), 0.5), ((22, 24), 0.8)]),
        "devices": [
            {"name": "Heater", "type": "heater", "power_w": 1500, "schedule": _hours((0, 8), (21, 24))},
            {"name": "Bedside light", "type": "light", "power_w": 40, "schedule": _hours((6, 8), (20, 24))},
        ],
    },
    {
        "name": "Home office",
        "weekday": _pattern(0.05, [((9, 12), 0.85), ((12, 13), 0.3), ((13, 18), 0.85), ((18, 19), 0.3)]),
        "weekend": _pattern(0.03, [((11, 14), 0.2)]),
        "devices": [
            {"name": "Desk fan", "type": "fan", "power_w": 48, "schedule": _hours((9, 19))},
            {"name": "Ceiling light", "type": "light", "power_w": 60, "schedule": _hours((8, 20))},
        ],
    },
]


def generate_demo(days=DEMO_DEFAULT_DAYS, seed=DEMO_DEFAULT_SEED, start_date=DEMO_START_DATE):
    """Rebuild data/demo.db from scratch and return a summary."""
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 31:
        raise ValidationError("days must be a whole number between 1 and 31.")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**31:
        raise ValidationError("seed must be a non-negative whole number.")
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    except (TypeError, ValueError):
        raise ValidationError("start_date must be YYYY-MM-DD.") from None

    reset_workspace("demo")
    conn = connect("demo")
    try:
        settings = get_settings(conn)
        rng = random.Random(seed)
        from .config import DEVICE_TYPES
        items = []
        with conn:
            for room in ROOMS:
                room_id = conn.execute("INSERT INTO rooms(name) VALUES (?)", (room["name"],)).lastrowid
                for device in room["devices"]:
                    preset = DEVICE_TYPES[device["type"]]
                    # Comfort value scales with power so every device has a sensible break-even.
                    scale = device["power_w"] / preset["power_w"]
                    conn.execute(
                        "INSERT INTO devices(room_id, name, type, power_w, comfort_value_per_hour, "
                        "startup_cost, schedule) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (room_id, device["name"], device["type"], device["power_w"],
                         round(preset["comfort_value_per_hour"] * scale, 2),
                         preset["startup_cost"], json.dumps(device["schedule"])))
                occupied = False
                steps = days * 24 * 60 // settings["interval_minutes"]
                for step in range(steps):
                    moment = start + timedelta(minutes=step * settings["interval_minutes"])
                    pattern = room["weekend"] if moment.weekday() >= 5 else room["weekday"]
                    if step == 0 or rng.random() > 0.75:
                        occupied = rng.random() < pattern[moment.hour]
                    hit = settings["motion_if_occupied"] if occupied else settings["motion_if_empty"]
                    motion = rng.random() < hit
                    items.append({"room_id": room_id, "ts": format_ts(moment), "motion": motion,
                                  "occupied": occupied})
            stored, decisions = ingest_readings(conn, items, "demo")
            meta = {"seed": seed, "days": days, "start_date": start_date,
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
            save_settings(conn, {"demo_meta": meta})
        return {**meta, "readings": len(stored), "decisions": len(decisions)}
    finally:
        conn.close()


def demo_meta(conn):
    row = conn.execute("SELECT value FROM settings WHERE key = 'demo_meta'").fetchone()
    return json.loads(row["value"]) if row else None
