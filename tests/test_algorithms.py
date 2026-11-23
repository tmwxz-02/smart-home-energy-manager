"""Unit tests for the three AI methods (pure functions, no database)."""

import itertools
import random
import unittest

from backend.algorithms.bayes import bayes_details, bayes_occupancy, filter_sequence, predict_occupancy
from backend.algorithms.hill_climbing import (exact_optimum, hill_climb, hill_climb_trace,
                                              optimise_schedule, schedule_cost, schedule_cost_parts)
from backend.algorithms.mdp import (break_even_probability, interval_costs, one_step_decision,
                                    qmdp_decision, value_iteration)

# The prototype's numbers: 48 W fan, 15-minute interval, 6 points per ON
# interval, 15 points per missed interval, transitions 0.8 / 0.2.
PROTO_COSTS = interval_costs(48, 15, tariff=500, comfort_value_per_hour=60, startup_cost=0)


class BayesTests(unittest.TestCase):
    def test_prototype_values_are_preserved(self):
        self.assertAlmostEqual(bayes_occupancy(0.75, True, 0.9, 0.2), 0.675 / 0.725)
        self.assertAlmostEqual(bayes_occupancy(0.75, False, 0.9, 0.2), 0.075 / 0.275)
        self.assertAlmostEqual(bayes_occupancy(0.75, False, 0.9, 0.2), 0.273, places=3)

    def test_evidence_is_total_probability(self):
        details = bayes_details(0.3, True, 0.8, 0.1)
        self.assertAlmostEqual(details["evidence"], 0.8 * 0.3 + 0.1 * 0.7)

    def test_no_motion_lowers_but_never_zeroes(self):
        posterior = bayes_occupancy(0.99, False, 0.9, 0.2)
        self.assertLess(posterior, 0.99)
        self.assertGreater(posterior, 0.0)

    def test_prediction_is_markov_step(self):
        self.assertAlmostEqual(predict_occupancy(0.931, 0.8, 0.2), 0.8 * 0.931 + 0.2 * 0.069, places=6)
        self.assertAlmostEqual(predict_occupancy(1.0, 0.85, 0.1), 0.85)
        self.assertAlmostEqual(predict_occupancy(0.0, 0.85, 0.1), 0.1)

    def test_filter_chains_predictions(self):
        rows = filter_sequence(0.5, [True, False, False], 0.9, 0.2, 0.85, 0.1)
        self.assertAlmostEqual(rows[1]["prior"], rows[0]["predicted"])
        self.assertAlmostEqual(rows[2]["prior"], rows[1]["predicted"])
        self.assertGreater(rows[1]["prior"], rows[2]["prior"])   # two misses lower the belief

    def test_invalid_prior_is_rejected(self):
        with self.assertRaises(ValueError):
            bayes_details(1.5, True, 0.9, 0.2)


class MdpTests(unittest.TestCase):
    def test_costs_scale_with_power_and_interval(self):
        fan = interval_costs(48, 15, 25, 3)
        heater = interval_costs(1500, 30, 25, 90)
        self.assertAlmostEqual(fan["energy_kwh"], 0.012)            # 48 W x 0.25 h
        self.assertAlmostEqual(heater["energy_kwh"], 0.75)          # 1500 W x 0.5 h
        self.assertAlmostEqual(heater["energy"], 0.75 * 25)
        self.assertAlmostEqual(heater["comfort"], 45.0)

    def test_one_step_reproduces_prototype_interval_five(self):
        motion = one_step_decision(predict_occupancy(bayes_occupancy(0.75, True, 0.9, 0.2), 0.8, 0.2), PROTO_COSTS)
        self.assertAlmostEqual(motion["q"]["ON"], -6.0)
        self.assertAlmostEqual(motion["q"]["OFF"], -11.38, places=2)
        self.assertEqual(motion["action"], "ON")
        quiet = one_step_decision(predict_occupancy(bayes_occupancy(0.75, False, 0.9, 0.2), 0.8, 0.2), PROTO_COSTS)
        self.assertAlmostEqual(quiet["q"]["OFF"], -5.45, places=2)
        self.assertEqual(quiet["action"], "OFF")

    def test_tie_goes_to_on(self):
        self.assertEqual(break_even_probability(PROTO_COSTS), 0.4)
        self.assertEqual(one_step_decision(0.4, PROTO_COSTS)["action"], "ON")

    def test_horizon_one_equals_one_step_rule(self):
        for belief in [i / 20 for i in range(21)]:
            multi = qmdp_decision(belief, True, [("ON", "OFF")], PROTO_COSTS, 0.8, 0.2)
            single = one_step_decision(belief, PROTO_COSTS)
            self.assertEqual(multi["action"], single["action"], belief)
            self.assertAlmostEqual(multi["q"]["ON"], single["q"]["ON"])
            self.assertAlmostEqual(multi["q"]["OFF"], single["q"]["OFF"])

    def test_without_startup_cost_planning_does_not_change_the_decision(self):
        # The action does not influence future states, so lookahead cannot help.
        for belief in [i / 20 for i in range(21)]:
            for was_on in (True, False):
                multi = qmdp_decision(belief, was_on, [("ON", "OFF")] * 6, PROTO_COSTS, 0.8, 0.2)
                self.assertEqual(multi["action"], one_step_decision(belief, PROTO_COSTS)["action"])

    def test_startup_cost_makes_the_decision_sequential(self):
        costs = interval_costs(48, 15, 25, 3, startup_cost=0.3)
        belief = 0.305
        self.assertEqual(one_step_decision(belief, costs)["action"], "OFF")
        keep = qmdp_decision(belief, True, [("ON", "OFF")] * 4, costs, 0.85, 0.1)
        self.assertEqual(keep["action"], "ON")      # restarting later would cost more
        cold = qmdp_decision(belief, False, [("ON", "OFF")] * 4, costs, 0.85, 0.1)
        self.assertEqual(cold["action"], "OFF")     # starting now costs the start-up

    def test_outside_schedule_only_off_is_possible(self):
        result = qmdp_decision(0.99, False, [("OFF",)], PROTO_COSTS, 0.8, 0.2)
        self.assertEqual(result["action"], "OFF")

    def test_value_iteration_matches_hand_computation(self):
        # H = 2, no start-up cost, occupied state: Q0(occ, ON) = -6 + E[V1].
        q0, values = value_iteration([("ON", "OFF")] * 2, PROTO_COSTS, 0.8, 0.2)
        v1_occ = max(-6.0, -15.0)
        v1_empty = max(-6.0, 0.0)
        expected = -6.0 + 0.8 * v1_occ + 0.2 * v1_empty
        self.assertAlmostEqual(q0[(1, True)]["ON"], expected)
        self.assertEqual(values[2][(1, True)], 0.0)

    def test_value_iteration_equals_brute_force_expectimax(self):
        costs = interval_costs(1200, 15, 25, 75, startup_cost=4)
        allowed = [("ON", "OFF"), ("ON", "OFF"), ("OFF",), ("ON", "OFF")]

        def best(k, occupied, was_on):
            if k == len(allowed):
                return 0.0
            p = 0.85 if occupied else 0.1
            options = []
            for action in allowed[k]:
                if action == "ON":
                    r = -costs["energy"] - (0 if was_on else costs["startup"])
                else:
                    r = -costs["comfort"] if occupied else 0.0
                on = action == "ON"
                options.append(r + p * best(k + 1, 1, on) + (1 - p) * best(k + 1, 0, on))
            return max(options)

        _, values = value_iteration(allowed, costs, 0.85, 0.1)
        for occupied, was_on in itertools.product((1, 0), (True, False)):
            self.assertAlmostEqual(values[0][(occupied, was_on)], best(0, occupied, was_on))


class HillClimbingTests(unittest.TestCase):
    def test_prototype_local_optimum_example(self):
        # Index 4 (cost 0) is the global best, but index 2 (cost 4) blocks the way.
        self.assertEqual(hill_climb([3, 2, 4, 1, 0]), [0, 1])
        self.assertEqual(hill_climb([53.10, 49.35, 45.60, 43.65, 44.85]), [0, 1, 2, 3])

    def test_cost_function_parts(self):
        priors = [0.5] * 24
        schedule = [1 if 8 <= h < 12 else 0 for h in range(24)]
        parts = schedule_cost_parts(schedule, priors, energy_cost_h=2.0, comfort_cost_h=10.0, startup_cost=1.0)
        self.assertEqual(parts["starts"], 1)
        self.assertAlmostEqual(parts["energy"], 8.0)
        self.assertAlmostEqual(parts["discomfort"], 20 * 0.5 * 10.0)
        self.assertAlmostEqual(parts["total"], 8.0 + 100.0 + 1.0)

    def test_starts_are_counted_cyclically(self):
        overnight = [1 if h >= 22 or h < 6 else 0 for h in range(24)]
        self.assertEqual(schedule_cost_parts(overnight, [0.5] * 24, 1, 1, 1)["starts"], 1)
        self.assertEqual(schedule_cost_parts([1] * 24, [0.5] * 24, 1, 1, 1)["starts"], 0)

    def test_result_is_a_local_optimum(self):
        rng = random.Random(3)
        priors = [rng.random() for _ in range(24)]

        def cost(s):
            return schedule_cost(s, priors, 2.0, 5.0, 3.0)

        final, steps, _, reason = hill_climb_trace([0] * 24, cost)
        self.assertEqual(reason, "local_optimum")
        for hour in range(24):
            neighbour = final.copy()
            neighbour[hour] = 1 - neighbour[hour]
            self.assertGreaterEqual(cost(neighbour), cost(final) - 1e-12)
        self.assertTrue(all(s["improvement"] > 0 for s in steps[1:]))   # strictly downhill

    def test_exact_optimum_matches_brute_force(self):
        rng = random.Random(11)
        for _ in range(5):
            priors = [rng.random() for _ in range(10)]
            brute = min(itertools.product((0, 1), repeat=10),
                        key=lambda s: schedule_cost(list(s), priors, 2.0, 5.0, 4.0))
            _, exact_cost = exact_optimum(priors, 2.0, 5.0, 4.0)
            self.assertAlmostEqual(exact_cost, schedule_cost(list(brute), priors, 2.0, 5.0, 4.0))

    def test_without_startup_cost_hill_climbing_is_exact(self):
        priors = [0.1] * 8 + [0.9] * 10 + [0.3] * 6
        result = optimise_schedule(priors, 2.0, 5.0, 0.0, [0] * 24, restarts=0)
        self.assertTrue(result["found_exact"])
        self.assertEqual(result["best"]["schedule"], [1 if p * 5.0 > 2.0 else 0 for p in priors])

    def test_restarts_can_escape_a_poor_local_optimum(self):
        # High start-up cost and two separated busy periods: single flips get stuck.
        priors = [0.05] * 24
        for hour in list(range(7, 9)) + list(range(18, 23)):
            priors[hour] = 0.95
        start = [1 if 7 <= h < 9 else 0 for h in range(24)]
        single = optimise_schedule(priors, 2.0, 6.0, 9.0, start, restarts=0)
        many = optimise_schedule(priors, 2.0, 6.0, 9.0, start, restarts=20, seed=1)
        self.assertFalse(single["found_exact"])
        self.assertGreater(single["gap_to_exact"], 0)
        self.assertLessEqual(many["best"]["total"], single["best"]["total"])
        self.assertTrue(many["found_exact"])

    def test_same_seed_same_result(self):
        priors = [random.Random(5).random() for _ in range(24)]
        a = optimise_schedule(priors, 2.0, 5.0, 3.0, [0] * 24, restarts=5, seed=7)
        b = optimise_schedule(priors, 2.0, 5.0, 3.0, [0] * 24, restarts=5, seed=7)
        self.assertEqual(a["best"], b["best"])


if __name__ == "__main__":
    unittest.main()
