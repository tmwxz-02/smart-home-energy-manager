"""Console version: the worked examples of the three methods, without a browser.

Useful as a fallback during the defense: ``python main.py``.
"""

import os
import tempfile

from .algorithms.bayes import bayes_details, predict_occupancy
from .algorithms.hill_climbing import hill_climb, optimise_schedule
from .algorithms.mdp import interval_costs, one_step_decision, qmdp_decision
from .brief import print_report


def line(title):
    print("\n" + title)
    print("-" * len(title))


def main():
    print_report()
    print()
    print("=" * 78)
    print("Smart Home Energy Manager - worked examples (all numbers are model assumptions)")

    line("1) Bayes + MDP: 48 W fan, 15-minute interval, prior 0.75")
    hit, false_alarm, stay, arrive = 0.90, 0.20, 0.85, 0.10
    tariff, comfort, startup = 25.0, 3.0, 0.3
    costs = interval_costs(48, 15, tariff, comfort, startup)
    print(f"energy cost per interval = 0.048 kW x 0.25 h x {tariff} = {costs['energy']:.3f} KZT;"
          f" discomfort if OFF and occupied = {comfort} x 0.25 = {costs['comfort']:.3f} KZT")
    for motion in (True, False):
        b = bayes_details(0.75, motion, hit, false_alarm)
        predicted = predict_occupancy(b["posterior"], stay, arrive)
        single = one_step_decision(predicted, costs)
        multi = qmdp_decision(predicted, True, [("ON", "OFF")] * 4, costs, stay, arrive)
        print(f"{'motion   ' if motion else 'no motion'}: P(reading)={b['evidence']:.3f} posterior={b['posterior']:.3f}"
              f" P(occ during interval)={predicted:.3f} | one-step ON {single['q']['ON']:.3f} /"
              f" OFF {single['q']['OFF']:.3f} -> {single['action']} | value iteration H=4"
              f" (device was ON) ON {multi['q']['ON']:.3f} / OFF {multi['q']['OFF']:.3f} -> {multi['action']}")
    print("With no motion the one-step rule switches OFF, but planning 4 intervals ahead keeps the fan ON:")
    print("switching off now would probably mean paying the start-up cost again soon.")

    line("2) Hill climbing on a 1-D list (prototype example of a local optimum)")
    print("costs [3, 2, 4, 1, 0] -> visited indices", hill_climb([3, 2, 4, 1, 0]),
          "(stops at index 1; the best index 4 is never reached)")

    line("3) Hill climbing on a 24-hour schedule (illustrative costs, two busy periods)")
    priors = [0.05] * 24
    for hour in list(range(7, 9)) + list(range(18, 23)):
        priors[hour] = 0.95
    start = [1 if 7 <= h < 9 else 0 for h in range(24)]
    energy_h, comfort_h, start_cost = 2.0, 6.0, 9.0   # per ON hour, per occupied hour OFF, per start
    for restarts in (0, 10):
        result = optimise_schedule(priors, energy_h, comfort_h, start_cost, start, restarts=restarts, seed=1)
        on = [h for h, v in enumerate(result["best"]["schedule"]) if v]
        print(f"restarts={restarts:2d}: best cost {result['best']['total']:.2f}, exact optimum "
              f"{result['exact']['total']:.2f}, gap {result['gap_to_exact']:.2f}, ON hours {on}")
    print("Started from the morning-only schedule, single-hour flips cannot add the evening block:")
    print("one evening hour adds 2 (energy) + 9 (start-up) = 11 but removes only 0.95 x 6 = 5.7 of")
    print("expected discomfort. Only the whole 5-hour block pays off, so a random restart is needed.")

    line("4) Demo data")
    folder = tempfile.mkdtemp(prefix="shem-cli-")
    os.environ["SHEM_DATA_DIR"] = folder
    from . import analytics, db, demo
    info = demo.generate_demo()
    conn = db.connect("demo")
    try:
        total = analytics.summary(conn)["total"]
        print(f"synthetic, seed {info['seed']}, {info['days']} days: {info['readings']} readings, "
              f"{info['decisions']} decisions")
        print(f"estimated energy: AI {total['ai_kwh']:.2f} kWh vs schedule {total['base_kwh']:.2f} kWh "
              f"({total['saved_pct']:.1f}% less); occupied-but-OFF {total['ai_missed_min']} device-min "
              f"vs {total['base_missed_min']}")
        for row in analytics.compare_strategies(conn)["strategies"]:
            print(f"  {row['label']:<32} {row['kwh']:8.2f} kWh  starts {row['starts']:4d}  "
                  f"missed {row['missed_min']:5d} min  on-while-empty {row['wasted_min']:5d} min")
    finally:
        conn.close()
    print("\n(Generated in a temporary folder; your data/ folder was not touched.)")
