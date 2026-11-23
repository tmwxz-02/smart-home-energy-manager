"""Topic 12 exactly as the course brief states it (MiniAI_FPTopics, topic 12).

    Scenario    A home agent controls one appliance.
    Hill climbing  choose the lowest-cost of 5 operating schedules.
    Bayesian inference  infer whether the room is occupied from a sensor.
    MDP         choose Keep On or Turn Off with 2 states.
    Small-scale setup   one device; 5 schedules; 2 occupancy states.
    Expected output     best schedule, occupancy estimate, action.

The full application (rooms, many devices, 24-hour schedules, value iteration)
generalises this. This module keeps the brief's tiny inputs so every number
can be checked by hand during the defense, and it reuses the SAME algorithm
functions as the application (backend/algorithms), so the two cannot drift
apart.

Every number below is a stated ASSUMPTION (toy model), not a measurement.
"""

from .algorithms.bayes import bayes_details, predict_occupancy
from .algorithms.mdp import OFF, ON, interval_costs, one_step_decision, qmdp_decision

# ---------------------------------------------------------------- inputs
DEVICE = {"name": "Living-room fan", "power_w": 48}
START_TIME = "18:00"
INTERVAL_MINUTES = 15
INTERVALS = 8                       # 18:00-20:00, 8 intervals of 15 minutes
TARIFF = 25.0                       # KZT per kWh
COMFORT_PER_HOUR = 3.0              # KZT: value of one hour of cooling for a person present
STARTUP_COST = 0.3                  # KZT per OFF->ON switch
MOTION_IF_OCCUPIED = 0.90           # sensor hit rate
MOTION_IF_EMPTY = 0.20              # sensor false-alarm rate
STAY_OCCUPIED = 0.85                # transition table, independent of the action
BECOME_OCCUPIED = 0.10

# P(occupied) for each interval from earlier days (the "prior" the agent has
# before it sees today's sensor).
PRIORS = (0.10, 0.20, 0.75, 0.75, 0.75, 0.55, 0.40, 0.15)
# Today's motion readings (what the sensor reports) and the true occupancy.
# The truth is used ONLY to evaluate the result, never to decide.
READINGS = (False, False, True, True, False, False, False, False)
TRUTH = (False, False, True, True, True, False, False, False)

# The 5 candidate operating schedules (interval numbers, 1-based), ordered from
# narrowest to broadest. Adjacent candidates differ by one interval, so they
# are the neighbours for hill climbing.
SCHEDULES = (
    (4,),
    (3, 4),
    (3, 4, 5),
    (3, 4, 5, 6),
    (2, 3, 4, 5, 6),
)

DEFAULT_START = 1                   # hill climbing starts from the narrowest schedule
DEFAULT_FOCUS = 5                   # interval used for the single Bayes + MDP example


def costs():
    """Money cost of one 15-minute interval for the fan."""
    return interval_costs(DEVICE["power_w"], INTERVAL_MINUTES, TARIFF, COMFORT_PER_HOUR,
                          STARTUP_COST)


def interval_label(number):
    start_h, start_m = map(int, START_TIME.split(":"))
    begin = start_h * 60 + start_m + (number - 1) * INTERVAL_MINUTES
    end = begin + INTERVAL_MINUTES
    return f"{begin // 60:02d}:{begin % 60:02d}-{end // 60:02d}:{end % 60:02d}"


# ---------------------------------------------------------------- 1. hill climbing
def schedule_cost(schedule, priors=PRIORS):
    """Expected cost of one evening (KZT) before any sensor reading.

    cost = sum over ON intervals of the energy cost
         + sum over OFF intervals of P(occupied) x discomfort cost
         + start-up cost x number of OFF->ON switches
    """
    c = costs()
    energy = sum(c["energy"] for k in range(1, INTERVALS + 1) if k in schedule)
    discomfort = sum(priors[k - 1] * c["comfort"] for k in range(1, INTERVALS + 1)
                     if k not in schedule)
    starts = sum(1 for k in range(1, INTERVALS + 1)
                 if k in schedule and (k - 1) not in schedule)
    return {"energy": energy, "discomfort": discomfort, "starts": starts,
            "startup": starts * c["startup"], "total": energy + discomfort + starts * c["startup"]}


def hill_climb(start=DEFAULT_START, priors=PRIORS):
    """Hill climbing over the 5 candidates (neighbours = adjacent candidates).

    From the current candidate, evaluate both neighbours; move to the cheaper
    one only if it is STRICTLY cheaper than the current candidate; otherwise stop.
    """
    if start not in range(1, len(SCHEDULES) + 1):
        raise ValueError(f"start must be between 1 and {len(SCHEDULES)}")
    totals = [schedule_cost(s, priors)["total"] for s in SCHEDULES]
    current = start - 1
    steps = []
    while True:
        neighbours = [i for i in (current - 1, current + 1) if 0 <= i < len(SCHEDULES)]
        best = min(neighbours, key=lambda i: totals[i])
        moved = totals[best] < totals[current] - 1e-12
        steps.append({
            "at": current + 1, "cost": totals[current],
            "neighbours": [{"number": i + 1, "cost": totals[i]} for i in neighbours],
            "moved_to": best + 1 if moved else None,
            "explanation": (f"Schedule {best + 1} costs {totals[best]:.4f} < {totals[current]:.4f}: move."
                            if moved else
                            f"No neighbour is cheaper than {totals[current]:.4f}: local optimum, stop."),
        })
        if not moved:
            break
        current = best
    exhaustive = min(range(len(SCHEDULES)), key=lambda i: totals[i]) + 1
    return {"path": [step["at"] for step in steps], "steps": steps, "best": current + 1,
            "evaluations": 1 + sum(len(step["neighbours"]) for step in steps),
            "exhaustive_best": exhaustive, "is_global_optimum": current + 1 == exhaustive}


def candidates(priors=PRIORS):
    rows = []
    for number, schedule in enumerate(SCHEDULES, start=1):
        rows.append({"number": number, "intervals": list(schedule),
                     "times": f"{interval_label(schedule[0])[:5]}-{interval_label(schedule[-1])[6:]}",
                     **schedule_cost(schedule, priors)})
    return rows


# ---------------------------------------------------------------- 2. Bayes
def bayes_step(focus=DEFAULT_FOCUS, motion=None):
    """One prior + one sensor observation -> P(occupied), then one prediction step."""
    if focus not in range(1, INTERVALS + 1):
        raise ValueError(f"interval must be between 1 and {INTERVALS}")
    motion = READINGS[focus - 1] if motion is None else bool(motion)
    prior = PRIORS[focus - 1]
    details = bayes_details(prior, motion, MOTION_IF_OCCUPIED, MOTION_IF_EMPTY)
    predicted = predict_occupancy(details["posterior"], STAY_OCCUPIED, BECOME_OCCUPIED)
    return {"interval": focus, "time": interval_label(focus), "motion": motion, **details,
            "predicted": predicted}


# ---------------------------------------------------------------- 3. MDP
def mdp_step(belief, was_on=True):
    """2 states (occupied / empty) x 2 actions (Keep On / Turn Off).

    One-step expected reward (one Bellman update with V_next = 0):
        Q(a) = P(occ) R(occ, a) + P(empty) R(empty, a)
    The larger Q wins; a tie keeps the fan on (comfort first).
    For comparison it also reports the application's planner: value
    iteration over 4 intervals with the start-up cost (QMDP belief).
    """
    c = costs()
    one = one_step_decision(belief, c)
    planner = qmdp_decision(belief, was_on, [(ON, OFF)] * 4, c, STAY_OCCUPIED, BECOME_OCCUPIED)
    name = {ON: "Keep On", OFF: "Turn Off"}
    return {
        "states": ["occupied", "empty"],
        "actions": ["Keep On", "Turn Off"],
        "rewards": {"Keep On": {"occupied": -c["energy"], "empty": -c["energy"]},
                    "Turn Off": {"occupied": -c["comfort"], "empty": 0.0}},
        "transitions": {"occupied": {"occupied": STAY_OCCUPIED, "empty": 1 - STAY_OCCUPIED},
                        "empty": {"occupied": BECOME_OCCUPIED, "empty": 1 - BECOME_OCCUPIED}},
        "belief": belief,
        "q": {"Keep On": one["q"][ON], "Turn Off": one["q"][OFF]},
        "action": name[one["action"]],
        "break_even": c["energy"] / c["comfort"],
        "planner": {"horizon": 4, "was_on": was_on, "startup_cost": c["startup"],
                    "q": {"Keep On": planner["q"][ON], "Turn Off": planner["q"][OFF]},
                    "action": name[planner["action"]]},
    }


# ---------------------------------------------------------------- evaluation
def evaluate(schedule, readings=READINGS, truth=TRUTH):
    """Run the evening three ways on the same readings and score them against the truth.

    * schedule only: ON exactly in the chosen schedule;
    * AI one-step: Bayes filter + one-step MDP inside the schedule;
    * AI planner: Bayes filter + value iteration (H = 4, start-up cost).
    As the brief asks, every interval uses ONE prior (the interval's
    P(occupied) from earlier days) and ONE sensor reading; the belief used
    for the decision is the posterior moved one step through the transition
    table. (The full application additionally chains consecutive readings,
    i.e. HMM forward filtering.)
    """
    c = costs()
    rows = []
    state = {"schedule": OFF, "one_step": OFF, "planner": OFF}
    totals = {key: {"wh": 0.0, "starts": 0, "missed_min": 0, "wasted_min": 0} for key in state}
    for k in range(1, INTERVALS + 1):
        prior = PRIORS[k - 1]
        details = bayes_details(prior, readings[k - 1], MOTION_IF_OCCUPIED, MOTION_IF_EMPTY)
        belief = predict_occupancy(details["posterior"], STAY_OCCUPIED, BECOME_OCCUPIED)
        inside = k in schedule
        allowed = [((ON, OFF) if (k + j) in schedule else (OFF,)) for j in range(4)]
        actions = {
            "schedule": ON if inside else OFF,
            "one_step": one_step_decision(belief, c)["action"] if inside else OFF,
            "planner": (qmdp_decision(belief, state["planner"] == ON, allowed, c,
                                      STAY_OCCUPIED, BECOME_OCCUPIED)["action"] if inside else OFF),
        }
        for key, action in actions.items():
            t = totals[key]
            if action == ON:
                t["wh"] += DEVICE["power_w"] * INTERVAL_MINUTES / 60
                t["starts"] += int(state[key] == OFF)
                t["wasted_min"] += 0 if truth[k - 1] else INTERVAL_MINUTES
            elif truth[k - 1] and inside:
                t["missed_min"] += INTERVAL_MINUTES
            state[key] = action
        rows.append({"interval": k, "time": interval_label(k), "inside": inside,
                     "motion": readings[k - 1], "truth": truth[k - 1], "prior": prior,
                     "posterior": details["posterior"], "belief": belief,
                     **{f"{key}_action": value for key, value in actions.items()}})
    for t in totals.values():
        t["cost"] = (t["wh"] / 1000 * TARIFF + t["starts"] * c["startup"]
                     + t["missed_min"] / 60 * COMFORT_PER_HOUR)
    return {"rows": rows, "totals": totals}


# ---------------------------------------------------------------- everything
def run(start=DEFAULT_START, focus=DEFAULT_FOCUS, motion=None):
    """The whole brief: hill climbing -> Bayes -> MDP -> evaluation."""
    search = hill_climb(start)
    best = SCHEDULES[search["best"] - 1]
    bayes = bayes_step(focus, motion)
    was_on = (focus - 1) in best
    mdp = mdp_step(bayes["predicted"], was_on=was_on)
    return {
        "assumptions": {
            "device": DEVICE, "start_time": START_TIME, "interval_minutes": INTERVAL_MINUTES,
            "intervals": INTERVALS, "tariff": TARIFF, "comfort_per_hour": COMFORT_PER_HOUR,
            "startup_cost": STARTUP_COST, "motion_if_occupied": MOTION_IF_OCCUPIED,
            "motion_if_empty": MOTION_IF_EMPTY, "stay_occupied": STAY_OCCUPIED,
            "become_occupied": BECOME_OCCUPIED, "priors": list(PRIORS),
            "readings": list(READINGS), "truth": list(TRUTH), "costs": costs(),
            "currency": "KZT",
        },
        "candidates": candidates(),
        "hill_climbing": search,
        "bayes": bayes,
        "mdp": mdp,
        "evaluation": evaluate(best),
        "output": {
            "best_schedule": search["best"],
            "best_schedule_times": candidates()[search["best"] - 1]["times"],
            "occupancy_estimate": bayes["posterior"],
            "action": mdp["action"],
        },
    }


def validate_request(body):
    """Validate the optional JSON body of POST /api/brief."""
    body = body if isinstance(body, dict) else {}
    out = {}
    for key, low, high in (("start", 1, len(SCHEDULES)), ("focus", 1, INTERVALS)):
        if key in body and body[key] is not None:
            value = body[key]
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"'{key}' must be a whole number between {low} and {high}.")
            out[key] = value
    if body.get("motion") is not None:
        if not isinstance(body["motion"], bool):
            raise ValueError("'motion' must be true or false.")
        out["motion"] = body["motion"]
    return out


def print_report(result=None):
    """Console version: input -> key steps -> output -> one-sentence explanation."""
    r = result or run()
    a = r["assumptions"]
    c = a["costs"]
    print("TOPIC 12 BRIEF - Mini Smart Home Energy Saver (toy inputs, all values are assumptions)")
    print(f"Device: {a['device']['name']}, {a['device']['power_w']} W; {a['intervals']} intervals x "
          f"{a['interval_minutes']} min from {a['start_time']}; tariff {a['tariff']} KZT/kWh")
    print(f"Energy cost per ON interval = {c['energy']:.3f} KZT; discomfort if OFF while occupied = "
          f"{c['comfort']:.3f} KZT; start-up = {c['startup']:.3f} KZT")

    print("\n[1] HILL CLIMBING - lowest-cost of 5 operating schedules")
    print("    input : priors P(occupied) per interval =", a["priors"])
    for row in r["candidates"]:
        print(f"    schedule {row['number']} {row['times']} intervals {row['intervals']}: energy "
              f"{row['energy']:.4f} + discomfort {row['discomfort']:.4f} + start-up {row['startup']:.4f}"
              f" = {row['total']:.4f}")
    for step in r["hill_climbing"]["steps"]:
        print(f"    step: at schedule {step['at']} -> {step['explanation']}")
    hc = r["hill_climbing"]
    print(f"    output: best schedule {hc['best']} (path {hc['path']}, {hc['evaluations']} evaluations;"
          f" exhaustive check: {hc['exhaustive_best']}, global optimum = {hc['is_global_optimum']})")
    print("    why   : each step keeps the cheaper neighbour, so the search stops at the schedule"
          " where adding or removing one interval no longer lowers the expected cost.")

    b = r["bayes"]
    print("\n[2] BAYESIAN INFERENCE - is the room occupied?")
    print(f"    input : interval {b['interval']} ({b['time']}), prior {b['prior']:.2f}, reading = "
          f"{'motion' if b['motion'] else 'no motion'}")
    print(f"    steps : P(reading) = {b['likelihood_occupied']:.2f} x {b['prior']:.2f} + "
          f"{b['likelihood_empty']:.2f} x {1 - b['prior']:.2f} = {b['evidence']:.4f}")
    print(f"            P(occ | reading) = {b['likelihood_occupied'] * b['prior']:.4f} / "
          f"{b['evidence']:.4f} = {b['posterior']:.4f}")
    print(f"            P(occ during next interval) = {b['posterior']:.4f} x {STAY_OCCUPIED} + "
          f"{1 - b['posterior']:.4f} x {BECOME_OCCUPIED} = {b['predicted']:.4f}")
    print(f"    output: occupancy estimate {b['posterior']:.3f}")
    print("    why   : the sensor misses still people 10% of the time, so 'no motion' lowers the"
          " belief but does not make it zero.")

    m = r["mdp"]
    print("\n[3] MDP - Keep On or Turn Off (2 states x 2 actions)")
    print(f"    input : belief P(occupied) = {m['belief']:.4f}; rewards Keep On "
          f"{m['rewards']['Keep On']['occupied']:.3f} (any state), Turn Off "
          f"{m['rewards']['Turn Off']['occupied']:.3f} if occupied / 0 if empty")
    print(f"    steps : Q(Keep On) = {m['q']['Keep On']:.4f};  Q(Turn Off) = {m['belief']:.4f} x "
          f"{m['rewards']['Turn Off']['occupied']:.3f} = {m['q']['Turn Off']:.4f}  "
          f"(break-even P = {m['break_even']:.2f})")
    print(f"    output: action = {m['action']}")
    print(f"    why   : P(occupied) {m['belief']:.3f} is below the break-even {m['break_even']:.2f},"
          " so the expected discomfort is cheaper than the electricity.")
    p = m["planner"]
    print(f"    (application planner, value iteration H = 4 with start-up cost, fan was "
          f"{'ON' if p['was_on'] else 'OFF'}: Keep On {p['q']['Keep On']:.4f} vs Turn Off "
          f"{p['q']['Turn Off']:.4f} -> {p['action']})")

    print("\n[4] RESULT - the same evening run three ways (truth used only for scoring)")
    labels = {"schedule": "Schedule only", "one_step": "AI, one-step MDP", "planner": "AI, planner H=4"}
    for key, t in r["evaluation"]["totals"].items():
        print(f"    {labels[key]:<18} energy {t['wh']:5.1f} Wh  starts {t['starts']}  "
              f"occupied-but-off {t['missed_min']:3d} min  on-while-empty {t['wasted_min']:3d} min  "
              f"total cost {t['cost']:.3f} KZT")
    o = r["output"]
    print(f"\nEXPECTED OUTPUT -> best schedule: {o['best_schedule']} ({o['best_schedule_times']}); "
          f"occupancy estimate: {o['occupancy_estimate']:.3f}; action: {o['action']}")
