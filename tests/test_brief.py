"""Tests for the Topic 12 brief walkthrough (backend/brief.py and /api/brief).

Expected numbers were computed by hand:
  energy per ON interval  = 0.048 kW x 0.25 h x 25 = 0.300 KZT
  discomfort per interval = 3 KZT/h x 0.25 h        = 0.750 KZT
  schedule 4 (intervals 3-6) = 4 x 0.3 + (0.1+0.2+0.4+0.15) x 0.75 + 0.3 = 2.1375
  prior 0.75, no motion: 0.075 / (0.075 + 0.2) = 0.2727; next = 0.3045
"""

import os
import shutil
import tempfile
import unittest
from itertools import combinations

from backend import brief


class BriefAlgorithmTests(unittest.TestCase):
    def test_interval_costs(self):
        c = brief.costs()
        self.assertAlmostEqual(c["energy"], 0.300)
        self.assertAlmostEqual(c["comfort"], 0.750)

    def test_candidate_costs_by_hand(self):
        totals = [row["total"] for row in brief.candidates()]
        for got, expected in zip(totals, [2.775, 2.5125, 2.25, 2.1375, 2.2875]):
            self.assertAlmostEqual(got, expected)

    def test_hill_climbing_path_and_stop(self):
        result = brief.hill_climb(1)
        self.assertEqual(result["path"], [1, 2, 3, 4])
        self.assertEqual(result["best"], 4)
        self.assertIsNone(result["steps"][-1]["moved_to"])
        self.assertTrue(result["is_global_optimum"])

    def test_every_start_reaches_a_local_optimum(self):
        totals = [row["total"] for row in brief.candidates()]
        for start in range(1, 6):
            best = brief.hill_climb(start)["best"] - 1
            for neighbour in (best - 1, best + 1):
                if 0 <= neighbour < 5:
                    self.assertLessEqual(totals[best], totals[neighbour])

    def test_hill_climbing_can_stop_in_a_local_optimum(self):
        # Interval 3 is never occupied, intervals 2, 5 and 6 always are. Adding
        # interval 3 (schedule 1 -> 2) costs +0.30, so hill climbing from
        # schedule 1 stops at once, although schedule 5 is cheaper overall.
        priors = (0.0, 1.0, 0.0, 0.5, 1.0, 1.0, 0.0, 0.0)
        result = brief.hill_climb(1, priors)
        self.assertEqual(result["path"], [1])
        self.assertEqual(result["exhaustive_best"], 5)
        self.assertFalse(result["is_global_optimum"])
        # Starting elsewhere (a restart) escapes the trap.
        self.assertEqual(brief.hill_climb(3, priors)["best"], 5)

    def test_best_candidate_is_close_to_unrestricted_optimum(self):
        # Brute force over every contiguous block of the 8 intervals: the brief's
        # best candidate (3-6) is also the best possible single block.
        best_block, best_cost = None, None
        for i, j in combinations(range(1, 10), 2):
            block = tuple(range(i, j))
            cost = brief.schedule_cost(block)["total"]
            if best_cost is None or cost < best_cost - 1e-12:
                best_block, best_cost = block, cost
        self.assertEqual(best_block, (3, 4, 5, 6))

    def test_bayes_step(self):
        b = brief.bayes_step(5)
        self.assertFalse(b["motion"])
        self.assertAlmostEqual(b["evidence"], 0.275)
        self.assertAlmostEqual(b["posterior"], 0.075 / 0.275)
        self.assertAlmostEqual(b["predicted"], b["posterior"] * 0.85 + (1 - b["posterior"]) * 0.10)
        self.assertAlmostEqual(brief.bayes_step(3)["posterior"], 0.675 / 0.725)

    def test_mdp_step_one_step_and_planner(self):
        m = brief.mdp_step(0.3045, was_on=True)
        self.assertAlmostEqual(m["q"]["Keep On"], -0.3)
        self.assertAlmostEqual(m["q"]["Turn Off"], -0.3045 * 0.75)
        self.assertEqual(m["action"], "Turn Off")
        self.assertAlmostEqual(m["break_even"], 0.4)
        self.assertEqual(m["planner"]["action"], "Keep On")   # start-up cost makes it stay ON
        self.assertEqual(brief.mdp_step(0.4)["action"], "Keep On")  # tie goes to Keep On
        self.assertEqual(brief.mdp_step(0.8)["action"], "Keep On")

    def test_evaluation_uses_truth_only_for_scoring(self):
        result = brief.evaluate(brief.SCHEDULES[3])
        totals = result["totals"]
        self.assertEqual(totals["schedule"]["wh"], 48.0)
        self.assertEqual(totals["schedule"]["wasted_min"], 15)
        self.assertEqual(totals["one_step"]["missed_min"], 15)
        self.assertEqual(totals["planner"]["missed_min"], 0)
        self.assertEqual(totals["planner"]["wasted_min"], 0)
        self.assertLess(totals["planner"]["cost"], totals["schedule"]["cost"])
        # Flipping the truth must not change any decision.
        flipped = brief.evaluate(brief.SCHEDULES[3], truth=tuple(not t for t in brief.TRUTH))
        for a, b in zip(result["rows"], flipped["rows"]):
            for key in ("schedule_action", "one_step_action", "planner_action"):
                self.assertEqual(a[key], b[key])

    def test_run_has_the_expected_output_fields(self):
        out = brief.run()["output"]
        self.assertEqual(out["best_schedule"], 4)
        self.assertAlmostEqual(out["occupancy_estimate"], 0.2727, places=4)
        self.assertEqual(out["action"], "Turn Off")

    def test_validation(self):
        self.assertEqual(brief.validate_request(None), {})
        self.assertEqual(brief.validate_request({"start": 2, "focus": 3, "motion": True}),
                         {"start": 2, "focus": 3, "motion": True})
        for bad in ({"start": 0}, {"start": 6}, {"focus": 9}, {"start": "2"}, {"motion": 1},
                    {"start": True}):
            with self.assertRaises(ValueError):
                brief.validate_request(bad)


class BriefApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="shem-brief-")
        self.old = os.environ.get("SHEM_DATA_DIR")
        os.environ["SHEM_DATA_DIR"] = self.folder

    def tearDown(self):
        if self.old is None:
            os.environ.pop("SHEM_DATA_DIR", None)
        else:
            os.environ["SHEM_DATA_DIR"] = self.old
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_get_and_post(self):
        from backend.api import dispatch
        status, data = dispatch("GET", "/api/brief")
        self.assertEqual(status, 200)
        self.assertEqual(data["output"]["best_schedule"], 4)
        status, data = dispatch("POST", "/api/brief", body={"focus": 3, "motion": True})
        self.assertEqual(status, 200)
        self.assertEqual(data["output"]["action"], "Keep On")
        status, data = dispatch("POST", "/api/brief", body={"start": 9})
        self.assertEqual(status, 400)
        self.assertIn("start", data["error"])

    def test_allowed_in_read_only_mode(self):
        from backend import access
        old = os.environ.get("SHEM_READ_ONLY")
        os.environ["SHEM_READ_ONLY"] = "1"
        try:
            self.assertFalse(access.blocked_by_read_only("POST", "/api/brief"))
            self.assertTrue(access.blocked_by_read_only("POST", "/api/rooms"))
        finally:
            if old is None:
                os.environ.pop("SHEM_READ_ONLY", None)
            else:
                os.environ["SHEM_READ_ONLY"] = old


if __name__ == "__main__":
    unittest.main()
