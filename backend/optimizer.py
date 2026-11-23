"""Glue between the stored data and the AI methods for the Optimizer and
Methods pages: hill-climbing schedule search and a step-by-step Bayes + MDP
calculator."""

import json

from .algorithms.bayes import bayes_details, predict_occupancy
from .algorithms.hill_climbing import optimise_schedule
from .algorithms.mdp import (break_even_probability, interval_costs, one_step_decision,
                             qmdp_decision)
from .db import get_settings
from .priors import hourly_priors
from .services import NotFound, ValidationError, get_device, validate_schedule


def _int(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValidationError(f"{name} must be a whole number between {low} and {high}.")
    return value


def optimise(conn, body):
    body = body or {}
    device_id = _int(body.get("device_id"), "device_id", 1, 10**9)
    restarts = _int(body.get("restarts", 5), "restarts", 0, 50)
    seed = _int(body.get("seed", 42), "seed", 0, 2**31)
    device = get_device(conn, device_id)
    settings = get_settings(conn)
    priors = hourly_priors(conn, device["room_id"], settings)
    energy_h = device["power_w"] / 1000.0 * settings["tariff_per_kwh"]
    result = optimise_schedule([p["prior"] for p in priors], energy_h,
                               device["comfort_value_per_hour"], device["startup_cost"],
                               device["schedule"], restarts=restarts, seed=seed)
    learned = sum(1 for p in priors if p["source"] == "learned")
    result["priors"] = priors
    result["learned_hours"] = learned
    result["device"] = device
    result["currency"] = settings["currency"]
    result["break_even"] = (energy_h / device["comfort_value_per_hour"]
                            if device["comfort_value_per_hour"] > 0 else None)
    result["warning"] = (None if learned == 24 else
                         f"Only {learned} of 24 hours have enough readings; the other hours use the "
                         f"default prior {settings['default_prior']}. Add more readings for a "
                         "data-driven schedule.")
    # Keep the runs compact in the database: no per-step traces.
    stored = {key: value for key, value in result.items() if key not in ("runs", "device", "priors")}
    cursor = conn.execute("INSERT INTO optimizations(device_id, result) VALUES (?, ?)",
                          (device_id, json.dumps(stored)))
    conn.commit()
    result["optimization_id"] = cursor.lastrowid
    return result


def apply_schedule(conn, device_id, body):
    device = get_device(conn, device_id)
    schedule = validate_schedule((body or {}).get("schedule"))
    conn.execute("UPDATE devices SET schedule = ? WHERE id = ?", (json.dumps(schedule), device_id))
    optimization_id = (body or {}).get("optimization_id")
    if isinstance(optimization_id, int):
        conn.execute("UPDATE optimizations SET applied = 1 WHERE id = ? AND device_id = ?",
                     (optimization_id, device_id))
    conn.execute("INSERT INTO control_log(device_id, action, detail) VALUES (?, 'SCHEDULE', ?)",
                 (device_id, "Schedule replaced by the hill-climbing result"))
    conn.commit()
    return {**get_device(conn, device_id), "previous_schedule": device["schedule"]}


def explain(conn, body):
    """Bayes + MDP calculation for one hypothetical reading (Methods page)."""
    body = body or {}
    settings = get_settings(conn)
    prior = body.get("prior")
    if isinstance(prior, bool) or not isinstance(prior, (int, float)) or not 0.0 <= prior <= 1.0:
        raise ValidationError("prior must be a number between 0 and 1.")
    motion = body.get("motion")
    if not isinstance(motion, bool):
        raise ValidationError("motion must be true or false.")
    was_on = bool(body.get("was_on", True))
    device_id = body.get("device_id")
    if device_id:
        try:
            device = get_device(conn, device_id)
        except NotFound as error:
            raise ValidationError(str(error)) from None
    else:
        # The prototype's 48 W fan, with the current tariff.
        device = {"name": "48 W fan (prototype)", "power_w": 48.0,
                  "comfort_value_per_hour": 3.0, "startup_cost": 0.3, "schedule": [1] * 24}
    bayes = bayes_details(prior, motion, settings["motion_if_occupied"], settings["motion_if_empty"])
    predicted = predict_occupancy(bayes["posterior"], settings["stay_occupied"],
                                  settings["become_occupied"])
    costs = interval_costs(device["power_w"], settings["interval_minutes"], settings["tariff_per_kwh"],
                           device["comfort_value_per_hour"], device["startup_cost"])
    horizon = int(settings["horizon"])
    allowed = [("ON", "OFF")] * horizon
    multi = qmdp_decision(predicted, was_on, allowed, costs, settings["stay_occupied"],
                          settings["become_occupied"], settings["discount"])
    single = one_step_decision(predicted, costs)
    return {"device": {k: device[k] for k in ("name", "power_w", "comfort_value_per_hour",
                                               "startup_cost")},
            "settings": settings, "bayes": bayes, "predicted": predicted, "costs": costs,
            "break_even": break_even_probability(costs), "one_step": single, "mdp": multi,
            "was_on": was_on}
