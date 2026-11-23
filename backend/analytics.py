"""Analytics over the stored decision history, CSV report, strategy replay.

All energy values are ESTIMATES: rated power x time the virtual device was
ON. Costs are energy x the chosen tariff. Comfort is only reported when the
readings carry occupancy labels; without labels it is not estimated.
"""

import csv
import io

from .db import get_settings, rows
from .engine import Engine
from .priors import PriorCache
from .services import ValidationError, active_devices


def _where(date_from, date_to, room_id, device_id):
    clauses, params = ["1=1"], []
    if date_from:
        clauses.append("c.ts >= ?")
        params.append(f"{date_from}T00:00")
    if date_to:
        clauses.append("c.ts <= ?")
        params.append(f"{date_to}T23:59")
    if room_id:
        clauses.append("c.room_id = ?")
        params.append(room_id)
    if device_id:
        clauses.append("c.device_id = ?")
        params.append(device_id)
    return " AND ".join(clauses), params


AGGREGATE = """
    COUNT(*) AS decisions,
    COUNT(DISTINCT c.reading_id) AS intervals,
    COALESCE(SUM(c.energy_wh), 0) AS ai_wh,
    COALESCE(SUM(c.baseline_energy_wh), 0) AS base_wh,
    COALESCE(SUM(c.starts), 0) AS ai_starts,
    COALESCE(SUM(c.baseline_starts), 0) AS base_starts,
    COALESCE(SUM(c.action = 'ON'), 0) AS ai_on,
    COALESCE(SUM(c.action = 'OFF' AND c.scheduled = 1), 0) AS ai_skipped,
    COALESCE(SUM(c.mode = 'manual'), 0) AS manual,
    COALESCE(SUM(x.occupied IS NOT NULL), 0) AS labelled,
    COALESCE(SUM(CASE WHEN x.occupied = 1 AND c.scheduled = 1 AND c.action = 'OFF'
                      THEN c.interval_minutes ELSE 0 END), 0) AS ai_missed_min,
    COALESCE(SUM(CASE WHEN x.occupied = 1 AND c.scheduled = 1 AND c.baseline_action = 'OFF'
                      THEN c.interval_minutes ELSE 0 END), 0) AS base_missed_min,
    COALESCE(SUM(CASE WHEN x.occupied = 0 AND c.action = 'ON'
                      THEN c.interval_minutes ELSE 0 END), 0) AS ai_wasted_min,
    COALESCE(SUM(CASE WHEN x.occupied = 0 AND c.baseline_action = 'ON'
                      THEN c.interval_minutes ELSE 0 END), 0) AS base_wasted_min,
    COALESCE(SUM(CASE WHEN x.occupied IS NOT NULL AND c.scheduled = 1
                      THEN c.interval_minutes ELSE 0 END), 0) AS labelled_scheduled_min,
    MIN(c.ts) AS first_ts, MAX(c.ts) AS last_ts
"""


def _finish(row, tariff):
    row = dict(row)
    row["ai_kwh"] = row.pop("ai_wh") / 1000.0
    row["base_kwh"] = row.pop("base_wh") / 1000.0
    row["saved_kwh"] = row["base_kwh"] - row["ai_kwh"]
    row["saved_pct"] = (100.0 * row["saved_kwh"] / row["base_kwh"]) if row["base_kwh"] > 0 else None
    row["ai_cost"] = row["ai_kwh"] * tariff
    row["base_cost"] = row["base_kwh"] * tariff
    row["saved_cost"] = row["saved_kwh"] * tariff
    if not row.get("labelled"):
        for key in ("ai_missed_min", "base_missed_min", "ai_wasted_min", "base_wasted_min"):
            row[key] = None
    return row


def check_period(date_from, date_to):
    for value in (date_from, date_to):
        if value and (len(value) != 10 or value[4] != "-" or value[7] != "-"):
            raise ValidationError("Dates must be YYYY-MM-DD.")
    if date_from and date_to and date_from > date_to:
        raise ValidationError("The start date must not be after the end date.")


def summary(conn, date_from=None, date_to=None, room_id=None, device_id=None, tariff=None):
    check_period(date_from, date_to)
    settings = get_settings(conn)
    tariff = settings["tariff_per_kwh"] if tariff is None else tariff
    where, params = _where(date_from, date_to, room_id, device_id)
    base = f"FROM decisions c JOIN readings x ON x.id = c.reading_id WHERE {where}"
    total = _finish(conn.execute(f"SELECT {AGGREGATE} {base}", params).fetchone(), tariff)
    daily = [_finish(row, tariff) for row in conn.execute(
        f"SELECT substr(c.ts, 1, 10) AS day, {AGGREGATE} {base} GROUP BY day ORDER BY day", params)]
    per_device = [_finish(row, tariff) for row in conn.execute(
        f"SELECT c.device_id, d.name AS device_name, r.name AS room_name, d.power_w, {AGGREGATE} "
        f"FROM decisions c JOIN readings x ON x.id = c.reading_id JOIN devices d ON d.id = c.device_id "
        f"JOIN rooms r ON r.id = c.room_id WHERE {where} GROUP BY c.device_id "
        f"ORDER BY r.name, d.name", params)]
    hourly = rows(conn.execute(
        f"SELECT CAST(substr(c.ts, 12, 2) AS INTEGER) AS hour, SUM(c.energy_wh) / 1000.0 AS ai_kwh, "
        f"SUM(c.baseline_energy_wh) / 1000.0 AS base_kwh {base} GROUP BY hour ORDER BY hour", params))
    comfort_note = None
    if total["decisions"] and not total["labelled"]:
        comfort_note = ("Comfort cannot be evaluated for this period: the readings have no occupancy "
                        "labels. Add an 'occupied' column to imported CSV files or tick 'occupied' "
                        "when entering readings.")
    elif total["decisions"] and total["labelled"] < total["decisions"]:
        comfort_note = (f"Comfort figures use only the {total['labelled']} of {total['decisions']} "
                        "device-intervals whose reading has an occupancy label.")
    return {"period": {"from": date_from, "to": date_to}, "tariff": tariff,
            "currency": settings["currency"], "total": total, "daily": daily,
            "per_device": per_device, "hourly": hourly, "comfort_note": comfort_note,
            "energy_note": "Energy is estimated from rated power x ON time of virtual devices; "
                           "it is not a meter measurement."}


def report_csv(conn, **filters):
    data = summary(conn, **filters)
    cur = data["currency"]
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["section", "date", "room", "device", "intervals", "ai_kwh_estimated",
                     "schedule_kwh_estimated", "saved_kwh", "saved_percent", f"ai_cost_{cur}",
                     f"schedule_cost_{cur}", f"saved_cost_{cur}", "ai_starts", "schedule_starts",
                     "labelled_device_intervals", "ai_missed_occupied_min",
                     "schedule_missed_occupied_min", "ai_on_while_empty_min",
                     "schedule_on_while_empty_min"])

    def line(section, row, date="", room="", device=""):
        def fmt(value, digits=4):
            return "" if value is None else round(value, digits)
        writer.writerow([section, date, room, device, row["intervals"], fmt(row["ai_kwh"]),
                         fmt(row["base_kwh"]), fmt(row["saved_kwh"]), fmt(row["saved_pct"], 2),
                         fmt(row["ai_cost"], 2), fmt(row["base_cost"], 2), fmt(row["saved_cost"], 2),
                         row["ai_starts"], row["base_starts"], row["labelled"],
                         fmt(row["ai_missed_min"], 0), fmt(row["base_missed_min"], 0),
                         fmt(row["ai_wasted_min"], 0), fmt(row["base_wasted_min"], 0)])

    period = f"{data['period']['from'] or 'start'} to {data['period']['to'] or 'end'}"
    line("total", data["total"], date=period)
    for row in data["per_device"]:
        line("device", row, room=row["room_name"], device=row["device_name"])
    for row in data["daily"]:
        line("day", row, date=row["day"])
    writer.writerow([])
    writer.writerow(["note", f"Tariff {data['tariff']} {cur}/kWh. {data['energy_note']}"])
    if data["comfort_note"]:
        writer.writerow(["note", data["comfort_note"]])
    return output.getvalue()


def compare_strategies(conn, date_from=None, date_to=None, room_id=None, device_id=None, tariff=None):
    """Replay several strategies on the SAME stored readings with the current settings.

    Nothing is written. Manual overrides are ignored so the strategies are
    compared purely as control policies.
    """
    check_period(date_from, date_to)
    settings = get_settings(conn)
    tariff = settings["tariff_per_kwh"] if tariff is None else tariff
    query = "SELECT room_id, ts, motion, occupied FROM readings x WHERE 1=1"
    params = []
    if date_from:
        query += " AND ts >= ?"
        params.append(f"{date_from}T00:00")
    if date_to:
        query += " AND ts <= ?"
        params.append(f"{date_to}T23:59")
    if room_id:
        query += " AND room_id = ?"
        params.append(room_id)
    readings = rows(conn.execute(query + " ORDER BY ts, room_id", params))
    devices = [d for d in active_devices(conn) if (not device_id or d["id"] == device_id)
               and (not room_id or d["room_id"] == room_id)]
    if not readings or not devices:
        return {"strategies": [], "readings": len(readings), "devices": len(devices),
                "note": "No readings or devices in this selection."}
    labelled = sum(1 for r in readings if r["occupied"] is not None)
    policies = [("schedule", "Schedule only"), ("one_step", "AI: one-step MDP rule"),
                ("mdp", f"AI: value iteration, H = {settings['horizon']}")]
    if labelled == len(readings):
        policies.append(("oracle", "Oracle (knows true occupancy)"))
    devices_by_id = {d["id"]: d for d in devices}
    results = []
    for policy, label in policies:
        engine = Engine(settings, devices, PriorCache(conn, settings).get, policy=policy,
                        honour_manual=False)
        stats = {"energy_wh": 0.0, "starts": 0, "startup_cost": 0.0, "missed_min": 0,
                 "wasted_min": 0, "on_intervals": 0}
        for reading in readings:
            _, decisions = engine.process(reading)
            for decision in decisions:
                stats["energy_wh"] += decision["energy_wh"]
                stats["starts"] += decision["starts"]
                stats["startup_cost"] += decision["starts"] * devices_by_id[decision["device_id"]]["startup_cost"]
                stats["on_intervals"] += decision["action"] == "ON"
                occupied = reading["occupied"]
                if occupied == 1 and decision["scheduled"] and decision["action"] == "OFF":
                    stats["missed_min"] += decision["interval_minutes"]
                if occupied == 0 and decision["action"] == "ON":
                    stats["wasted_min"] += decision["interval_minutes"]
        kwh = stats["energy_wh"] / 1000.0
        results.append({"policy": policy, "label": label, "kwh": kwh, "cost": kwh * tariff,
                        "starts": stats["starts"], "startup_cost": stats["startup_cost"],
                        "on_intervals": stats["on_intervals"],
                        "missed_min": stats["missed_min"] if labelled else None,
                        "wasted_min": stats["wasted_min"] if labelled else None})
    baseline = results[0]["kwh"]
    for result in results:
        result["saved_kwh"] = baseline - result["kwh"]
        result["saved_pct"] = 100.0 * result["saved_kwh"] / baseline if baseline > 0 else None
    note = ("All strategies use the same readings, devices, schedules and current settings. "
            "Manual overrides are ignored in the replay.")
    if labelled == 0:
        note += " No occupancy labels: comfort is not evaluated and the oracle is not shown."
    elif labelled < len(readings):
        note += (f" Only {labelled} of {len(readings)} readings are labelled: comfort uses the labelled "
                 "ones and the oracle is not shown.")
    return {"strategies": results, "readings": len(readings), "devices": len(devices),
            "labelled": labelled, "tariff": tariff, "currency": settings["currency"], "note": note}
