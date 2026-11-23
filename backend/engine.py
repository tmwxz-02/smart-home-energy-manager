"""Decision engine: reading -> Bayes filter -> MDP -> action, for every device.

The same code is used for live decisions (stored in SQLite) and for the
"what-if" replay in Analytics, so both always follow identical rules.

Per reading (room r, interval start t):
1. Prior P(occupied at t):
   * if the room has a reading exactly one interval earlier: the filter's
     prediction from that reading's posterior (HMM forward step);
   * otherwise the hour-of-day prior learned from earlier days (priors.py).
2. Bayes update with the motion reading -> posterior.
3. Transition step -> belief b = P(occupied during the interval).
4. For each active device in the room:
   * baseline ("schedule only"): ON iff the hour is in the device schedule;
   * manual mode: the user's ON/OFF state;
   * auto mode, outside the schedule: OFF;
   * auto mode, inside the schedule: MDP (value iteration + QMDP).
   Energy = rated power x interval length, i.e. an ESTIMATE, not a measurement.
"""

from datetime import datetime, timedelta

from .algorithms.bayes import bayes_details, predict_occupancy
from .algorithms.mdp import OFF, ON, interval_costs, one_step_decision, qmdp_decision

TS_FORMAT = "%Y-%m-%dT%H:%M"
POLICIES = ("schedule", "one_step", "mdp", "oracle")


def parse_ts(ts):
    return datetime.strptime(ts, TS_FORMAT)


def format_ts(moment):
    return moment.strftime(TS_FORMAT)


def shift(ts, minutes):
    return format_ts(parse_ts(ts) + timedelta(minutes=minutes))


def model_params(settings):
    keys = ("tariff_per_kwh", "interval_minutes", "motion_if_occupied", "motion_if_empty",
            "stay_occupied", "become_occupied", "horizon", "discount")
    return {key: settings[key] for key in keys}


class Engine:
    """Processes readings in time order and keeps the filter / device state."""

    def __init__(self, settings, devices, prior_fn, policy="mdp", honour_manual=True):
        if policy not in POLICIES:
            raise ValueError(f"Unknown policy '{policy}'")
        self.settings = settings
        self.devices_by_room = {}
        for device in devices:
            self.devices_by_room.setdefault(device["room_id"], []).append(device)
        self.prior_fn = prior_fn
        self.policy = policy
        self.honour_manual = honour_manual
        self.last_reading = {}      # room_id -> (ts, predicted)
        self.device_state = {}      # device_id -> "ON" / "OFF" (strategy being run)
        self.baseline_state = {}    # device_id -> "ON" / "OFF" (schedule only)

    # ------------------------------------------------------------ belief
    def belief(self, room_id, ts, motion):
        s = self.settings
        previous = self.last_reading.get(room_id)
        if previous and previous[0] == shift(ts, -s["interval_minutes"]):
            prior, source = previous[1], "filter"
        else:
            prior, source = self.prior_fn(room_id, ts)
        details = bayes_details(prior, motion, s["motion_if_occupied"], s["motion_if_empty"])
        predicted = predict_occupancy(details["posterior"], s["stay_occupied"], s["become_occupied"])
        self.last_reading[room_id] = (ts, predicted)
        return {"prior": prior, "prior_source": source, "posterior": details["posterior"],
                "predicted": predicted, "evidence": details["evidence"]}

    # ------------------------------------------------------------ decision
    def allowed_actions(self, device, ts):
        """Allowed actions for each of the next H intervals (schedule constraint)."""
        s = self.settings
        allowed = []
        moment = parse_ts(ts)
        for k in range(int(s["horizon"])):
            hour = (moment + timedelta(minutes=k * s["interval_minutes"])).hour
            allowed.append((ON, OFF) if device["schedule"][hour] else (OFF,))
        return allowed

    def decide(self, device, ts, motion, belief, occupied=None):
        s = self.settings
        hour = int(ts[11:13])
        scheduled = bool(device["schedule"][hour])
        previous_state = self.device_state.get(device["id"], OFF)
        baseline_previous = self.baseline_state.get(device["id"], OFF)
        costs = interval_costs(device["power_w"], s["interval_minutes"], s["tariff_per_kwh"],
                               device["comfort_value_per_hour"], device["startup_cost"])
        baseline_action = ON if scheduled else OFF
        q = {}
        horizon = None
        mode = "auto"
        if self.honour_manual and device.get("mode") == "manual":
            mode = "manual"
            action = device.get("manual_state", OFF)
            explanation = (f"Manual mode: the user set this virtual device {action}. "
                           f"The AI did not decide; P(occupied during the interval) was "
                           f"{belief['predicted']:.2f} for reference.")
        elif self.policy == "schedule":
            action = baseline_action
            explanation = "Schedule-only strategy: ON exactly in scheduled hours."
        elif self.policy == "oracle":
            action = ON if (scheduled and occupied) else OFF
            explanation = "Oracle: uses the true occupancy label (evaluation only)."
        elif not scheduled:
            action = OFF
            explanation = (f"{hour:02d}:00-{(hour + 1) % 24:02d}:00 is outside the schedule. "
                           "Auto mode never starts a device outside its schedule, so it stays OFF.")
        elif self.policy == "one_step":
            result = one_step_decision(belief["predicted"], costs)
            q, action, horizon = result["q"], result["action"], 1
            explanation = self.explain(device, motion, belief, q, action, 1, previous_state, costs)
        else:
            result = qmdp_decision(belief["predicted"], previous_state == ON,
                                   self.allowed_actions(device, ts), costs,
                                   s["stay_occupied"], s["become_occupied"], s["discount"])
            q, action, horizon = result["q"], result["action"], result["horizon"]
            explanation = self.explain(device, motion, belief, q, action, horizon,
                                       previous_state, costs)
        minutes = s["interval_minutes"]
        decision = {
            "device_id": device["id"], "room_id": device["room_id"], "ts": ts,
            "interval_minutes": minutes, "mode": mode, "scheduled": int(scheduled),
            "motion": int(bool(motion)), "prior": belief["prior"],
            "posterior": belief["posterior"], "predicted": belief["predicted"],
            "previous_state": previous_state, "q_on": q.get(ON), "q_off": q.get(OFF),
            "horizon": horizon, "action": action, "baseline_action": baseline_action,
            "energy_wh": device["power_w"] * minutes / 60.0 if action == ON else 0.0,
            "baseline_energy_wh": device["power_w"] * minutes / 60.0 if baseline_action == ON else 0.0,
            "starts": int(action == ON and previous_state == OFF),
            "baseline_starts": int(baseline_action == ON and baseline_previous == OFF),
            "explanation": explanation,
        }
        self.device_state[device["id"]] = action
        self.baseline_state[device["id"]] = baseline_action
        return decision

    def explain(self, device, motion, belief, q, action, horizon, previous_state, costs):
        s = self.settings
        currency = s["currency"]
        source = {"filter": "predicted from the previous interval (Bayesian filter)",
                  "hourly": "hour-of-day prior learned from earlier days",
                  "default": "default prior, not enough history for this hour"}[belief["prior_source"]]
        parts = [
            f"Inside the schedule. Motion {'detected' if motion else 'not detected'}.",
            f"Prior P(occupied) = {belief['prior']:.2f} ({source}) -> posterior "
            f"{belief['posterior']:.2f} -> P(occupied during the next {s['interval_minutes']} min) "
            f"= {belief['predicted']:.2f}.",
        ]
        method = ("one-step expected reward" if horizon == 1 and self.policy == "one_step"
                  else f"value iteration over {horizon} interval(s), QMDP belief")
        parts.append(f"Expected value ({method}): ON {q[ON]:.2f}, OFF {q[OFF]:.2f} {currency} "
                     "(negative = expected cost).")
        diff = abs(q[ON] - q[OFF])
        if action == OFF:
            parts.append(f"OFF is expected to save {diff:.2f} {currency}: energy "
                         f"{costs['energy']:.2f} {currency} per interval outweighs the expected "
                         "discomfort.")
        else:
            reason = "the expected discomfort of switching off outweighs the energy cost"
            if previous_state == ON and costs["startup"] > 0:
                reason += f" (restarting later would cost {costs['startup']:.2f} {currency})"
            parts.append(f"ON is better by {diff:.2f} {currency}: {reason}.")
        return " ".join(parts)

    # ------------------------------------------------------------ batch
    def process(self, reading):
        """Process one reading dict {room_id, ts, motion, occupied?}."""
        belief = self.belief(reading["room_id"], reading["ts"], bool(reading["motion"]))
        decisions = [self.decide(device, reading["ts"], bool(reading["motion"]), belief,
                                 reading.get("occupied"))
                     for device in self.devices_by_room.get(reading["room_id"], [])]
        return belief, decisions
