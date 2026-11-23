"""Method 1 (local search): hill climbing for a device's daily schedule.

Problem formulation
* State       a daily schedule = 24 hourly slots, each ON (1) or OFF (0).
* Objective   expected daily cost in money units (lower is better):
                cost(s) = sum_h [ s_h x energy_cost_h
                                 + (1 - s_h) x P(occupied at hour h) x comfort_cost_h ]
                          + startup_cost x (number of OFF->ON switches, cyclic day)
              energy_cost_h  = power [kW] x 1 h x tariff
              comfort_cost_h = value of service [money/h] x 1 h
              P(occupied at hour h) is the hour-of-day prior learned from the
              room's stored readings (see backend/priors.py).
* Neighbours  every schedule that differs in exactly ONE hour (24 neighbours).
* Move rule   steepest ascent: evaluate all neighbours, move to the cheapest
              one only if it is STRICTLY cheaper than the current schedule.
* Stop        no neighbour is strictly cheaper (local optimum) or the
              iteration limit is reached.
* Restarts    the search starts from the device's current schedule and from
              several random schedules (seeded => reproducible); the best
              local optimum wins.

Without the start-up cost each hour could be decided independently and
hill climbing would always find the optimum. The start-up cost couples
neighbouring hours (one long block is cheaper than many short ones), which
creates local optima. To measure solution quality honestly we also compute
the exact optimum with dynamic programming (``exact_optimum``) and report
the gap.
"""

import random

HOURS = 24


def schedule_cost_parts(schedule, priors, energy_cost_h, comfort_cost_h, startup_cost):
    """Split the expected daily cost of a schedule into its three parts."""
    energy = sum(energy_cost_h for on in schedule if on)
    discomfort = sum(p * comfort_cost_h for on, p in zip(schedule, priors) if not on)
    starts = sum(1 for h in range(len(schedule)) if schedule[h] and not schedule[h - 1])
    if all(schedule):
        starts = 0
    return {"energy": energy, "discomfort": discomfort, "starts": starts,
            "startup": starts * startup_cost,
            "total": energy + discomfort + starts * startup_cost}


def schedule_cost(schedule, priors, energy_cost_h, comfort_cost_h, startup_cost):
    return schedule_cost_parts(schedule, priors, energy_cost_h, comfort_cost_h, startup_cost)["total"]


def hill_climb_trace(start, cost_fn, max_iterations=200):
    """Steepest-ascent hill climbing over single-hour flips.

    Returns (final schedule, steps, evaluations). Each step records the
    flipped hour, the cost after the move and the improvement.
    """
    current = list(start)
    current_cost = cost_fn(current)
    steps = [{"iteration": 0, "flipped_hour": None, "cost": current_cost, "improvement": 0.0}]
    evaluations = 1
    for iteration in range(1, max_iterations + 1):
        best_hour, best_cost = None, current_cost
        for hour in range(len(current)):
            neighbour = current.copy()
            neighbour[hour] = 0 if neighbour[hour] else 1
            cost = cost_fn(neighbour)
            evaluations += 1
            if cost < best_cost - 1e-12:
                best_hour, best_cost = hour, cost
        if best_hour is None:
            return current, steps, evaluations, "local_optimum"
        current[best_hour] = 0 if current[best_hour] else 1
        steps.append({"iteration": iteration, "flipped_hour": best_hour,
                      "now_on": bool(current[best_hour]), "cost": best_cost,
                      "improvement": current_cost - best_cost})
        current_cost = best_cost
    return current, steps, evaluations, "iteration_limit"


def hill_climb(costs, start_index=0):
    """Hill climbing on a 1-D list of costs (neighbours = adjacent indices).

    Kept from the prototype for teaching: it shows the local-optimum trap on
    a tiny example, e.g. costs [3, 2, 4, 1, 0] stop at index 1.
    """
    current = start_index
    path = [current]
    while True:
        neighbours = [i for i in (current - 1, current + 1) if 0 <= i < len(costs)]
        best = min(neighbours, key=lambda i: costs[i])
        if costs[best] < costs[current]:
            current = best
            path.append(current)
        else:
            return path


def exact_optimum(priors, energy_cost_h, comfort_cost_h, startup_cost):
    """Exact minimum-cost schedule by dynamic programming (cyclic day of len(priors) slots).

    The cost only couples neighbouring hours, so we fix the state of hour 23
    (which precedes hour 0 in a cyclic day) and run a 2-state DP over hours.
    """
    best = None
    for last in (0, 1):
        # dp[s] = (cost so far, schedule so far) with current hour in state s
        dp = {}
        for s in (0, 1):
            cost = _slot_cost(s, priors[0], energy_cost_h, comfort_cost_h)
            cost += startup_cost if (s == 1 and last == 0) else 0.0
            dp[s] = (cost, [s])
        for h in range(1, len(priors)):
            new = {}
            for s in (0, 1):
                options = []
                for prev in (0, 1):
                    cost = dp[prev][0] + _slot_cost(s, priors[h], energy_cost_h, comfort_cost_h)
                    cost += startup_cost if (s == 1 and prev == 0) else 0.0
                    options.append((cost, dp[prev][1] + [s]))
                new[s] = min(options, key=lambda item: item[0])
            dp = new
        candidate = dp[last]
        if best is None or candidate[0] < best[0] - 1e-12:
            best = candidate
    schedule = best[1]
    # Recompute with the shared cost function (handles the all-ON case).
    return schedule, schedule_cost(schedule, priors, energy_cost_h, comfort_cost_h, startup_cost)


def _slot_cost(on, prior, energy_cost_h, comfort_cost_h):
    return energy_cost_h if on else prior * comfort_cost_h


def optimise_schedule(priors, energy_cost_h, comfort_cost_h, startup_cost,
                      current_schedule, restarts=5, seed=42, max_iterations=200):
    """Run hill climbing from the current schedule and from random restarts."""
    if len(priors) != HOURS or len(current_schedule) != HOURS:
        raise ValueError("priors and schedule must have 24 hourly values")

    def cost_fn(schedule):
        return schedule_cost(schedule, priors, energy_cost_h, comfort_cost_h, startup_cost)

    rng = random.Random(seed)
    starts = [("current schedule", [1 if v else 0 for v in current_schedule])]
    for number in range(1, restarts + 1):
        starts.append((f"random restart {number}", [rng.randint(0, 1) for _ in range(HOURS)]))

    runs = []
    total_evaluations = 0
    for label, start in starts:
        final, steps, evaluations, reason = hill_climb_trace(start, cost_fn, max_iterations)
        total_evaluations += evaluations
        runs.append({"label": label, "start": start, "final": final, "steps": steps,
                     "start_cost": steps[0]["cost"], "final_cost": steps[-1]["cost"],
                     "iterations": len(steps) - 1, "evaluations": evaluations,
                     "stop_reason": reason})
    best_run = min(runs, key=lambda run: run["final_cost"])
    exact_schedule, exact_cost = exact_optimum(priors, energy_cost_h, comfort_cost_h, startup_cost)
    current_parts = schedule_cost_parts(starts[0][1], priors, energy_cost_h, comfort_cost_h,
                                        startup_cost)
    best_parts = schedule_cost_parts(best_run["final"], priors, energy_cost_h, comfort_cost_h,
                                     startup_cost)
    distinct_optima = len({tuple(run["final"]) for run in runs})
    return {
        "runs": runs,
        "best": {"label": best_run["label"], "schedule": best_run["final"], **best_parts},
        "current": {"schedule": starts[0][1], **current_parts},
        "exact": {"schedule": exact_schedule,
                  **schedule_cost_parts(exact_schedule, priors, energy_cost_h, comfort_cost_h,
                                        startup_cost)},
        "gap_to_exact": best_parts["total"] - exact_cost,
        "found_exact": abs(best_parts["total"] - exact_cost) < 1e-9,
        "distinct_local_optima": distinct_optima,
        "evaluations": total_evaluations,
        "parameters": {"energy_cost_h": energy_cost_h, "comfort_cost_h": comfort_cost_h,
                       "startup_cost": startup_cost, "restarts": restarts, "seed": seed},
    }
