"""CSV import of sensor readings.

Expected columns (header row required, comma or semicolon separated):

    timestamp,room,motion,occupied
    2026-11-10 08:00,Living room,1,1
    2026-11-10 08:15,Living room,0,

* timestamp  local time 'YYYY-MM-DD HH:MM' (or with 'T'), at the start of an
             interval (minutes must be a multiple of the interval length)
* room       name of an existing, non-archived room (case-insensitive)
* motion     1/0, true/false, yes/no
* occupied   OPTIONAL label, same values, or empty = unknown. Labels are
             used only to evaluate comfort, never by the AI.

The import is all-or-nothing: if any row is invalid nothing is stored and
every problem is reported with its line number.
"""

import csv
import io

from .config import MAX_CSV_BYTES, MAX_CSV_ROWS, MAX_ERRORS_SHOWN
from .db import get_settings
from .services import ValidationError, check_reading_time, ingest_readings

TRUE = {"1", "true", "yes", "y", "t"}
FALSE = {"0", "false", "no", "n", "f"}
REQUIRED = ("timestamp", "room", "motion")


def parse_bool(text, allow_empty=False):
    value = (text or "").strip().lower()
    if value in TRUE:
        return True
    if value in FALSE:
        return False
    if allow_empty and value in ("", "unknown", "na", "n/a", "-"):
        return None
    raise ValueError


def parse_csv(conn, content):
    """Validate the CSV text. Returns the list of reading dicts or raises ValidationError."""
    if not isinstance(content, str) or not content.strip():
        raise ValidationError("The file is empty.")
    if len(content.encode("utf-8")) > MAX_CSV_BYTES:
        raise ValidationError(f"The file is larger than {MAX_CSV_BYTES // (1024 * 1024)} MB.")
    content = content.lstrip("﻿")
    first_line = content.splitlines()[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    header = [cell.strip().lower() for cell in next(reader)]
    missing = [column for column in REQUIRED if column not in header]
    if missing:
        raise ValidationError(
            "The header row is missing column(s): " + ", ".join(missing) + ".",
            [f"Line 1 must be: timestamp,room,motion,occupied (found: {','.join(header)})."])
    index = {name: header.index(name) for name in header}
    settings = get_settings(conn)
    rooms = {row["name"].lower(): dict(row) for row in conn.execute("SELECT * FROM rooms")}
    active_names = sorted(r["name"] for r in rooms.values() if not r["archived"])

    errors, items, seen = [], [], {}
    total_errors = 0
    for line_number, cells in enumerate(reader, start=2):
        if not any(cell.strip() for cell in cells):
            continue
        if len(items) + total_errors >= MAX_CSV_ROWS:
            raise ValidationError(f"The file has more than {MAX_CSV_ROWS} rows.")
        problems = []

        def cell(name):
            position = index.get(name)
            return cells[position].strip() if position is not None and position < len(cells) else ""

        ts = None
        try:
            ts = check_reading_time(cell("timestamp"), settings["interval_minutes"])
        except ValidationError as error:
            problems.append(str(error) if cell("timestamp") else "timestamp is empty.")
        room_name = cell("room")
        room = rooms.get(room_name.lower())
        if not room_name:
            problems.append("room is empty.")
        elif room is None:
            problems.append(f"room '{room_name}' does not exist. Create it on the Rooms & devices "
                            f"page or fix the name (existing: {', '.join(active_names) or 'none'}).")
        elif room["archived"]:
            problems.append(f"room '{room_name}' is archived.")
        try:
            motion = parse_bool(cell("motion"))
        except ValueError:
            motion = None
            problems.append(f"motion '{cell('motion')}' must be 1/0, true/false or yes/no.")
        occupied = None
        if "occupied" in index:
            try:
                occupied = parse_bool(cell("occupied"), allow_empty=True)
            except ValueError:
                problems.append(f"occupied '{cell('occupied')}' must be 1/0, true/false, yes/no or empty.")
        if not problems:
            key = (room["id"], ts)
            if key in seen:
                problems.append(f"duplicate of line {seen[key]} (same room and time).")
            elif conn.execute("SELECT 1 FROM readings WHERE room_id = ? AND ts = ?", key).fetchone():
                problems.append(f"a reading for {room['name']} at {ts.replace('T', ' ')} is already stored.")
            else:
                seen[key] = line_number
        if problems:
            total_errors += 1
            if len(errors) < MAX_ERRORS_SHOWN:
                errors.append(f"Line {line_number}: " + " ".join(problems))
            continue
        items.append({"room_id": room["id"], "ts": ts, "motion": motion, "occupied": occupied})

    if total_errors:
        more = total_errors - len(errors)
        if more > 0:
            errors.append(f"... and {more} more invalid row(s).")
        raise ValidationError(f"Nothing was imported: {total_errors} row(s) are invalid. "
                              "Fix them and import the file again.", errors)
    if not items:
        raise ValidationError("The file has a header but no data rows.")
    return items


def import_csv(conn, filename, content):
    if not isinstance(filename, str) or not filename.strip():
        filename = "upload.csv"
    items = parse_csv(conn, content)
    with conn:
        cursor = conn.execute("INSERT INTO imports(filename, rows) VALUES (?, ?)",
                              (filename.strip()[:120], len(items)))
        stored, decisions = ingest_readings(conn, items, "csv", cursor.lastrowid)
    timestamps = [item["ts"] for item in items]
    return {
        "import_id": cursor.lastrowid,
        "filename": filename,
        "rows": len(stored),
        "labelled": sum(1 for item in items if item["occupied"] is not None),
        "rooms": len({item["room_id"] for item in items}),
        "from": min(timestamps), "to": max(timestamps),
        "decisions": len(decisions),
        "ai_on": sum(1 for d in decisions if d["action"] == "ON"),
        "ai_off": sum(1 for d in decisions if d["action"] == "OFF"),
    }
