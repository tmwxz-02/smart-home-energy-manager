"""End-to-end tests of the application logic on a temporary SQLite folder.

Covers the full user scenario (room -> device -> reading -> AI decision ->
history -> analytics -> CSV report), persistence after reconnecting, CSV
import errors, units, manual control, archiving, demo separation and
reproducibility, and that the replay uses the same rules as live decisions.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class TempDataMixin:
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="shem-test-")
        self.old = os.environ.get("SHEM_DATA_DIR")
        os.environ["SHEM_DATA_DIR"] = self.folder
        from backend import db
        self.db = db
        self.conn = db.connect("home")

    def tearDown(self):
        self.conn.close()
        if self.old is None:
            os.environ.pop("SHEM_DATA_DIR", None)
        else:
            os.environ["SHEM_DATA_DIR"] = self.old
        shutil.rmtree(self.folder, ignore_errors=True)

    def make_home(self, schedule=None, power=1200):
        from backend import services
        room = services.create_room(self.conn, {"name": "Living room"})
        device = services.create_device(self.conn, {
            "name": "AC", "type": "ac", "room_id": room["id"], "power_w": power,
            "schedule": schedule or [1] * 24})
        return room, device


class ScenarioTests(TempDataMixin, unittest.TestCase):
    def test_full_user_scenario(self):
        from backend import analytics, services
        room, device = self.make_home(schedule=[1 if 18 <= h < 23 else 0 for h in range(24)])
        result = services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 18:00",
                                                  "motion": True, "occupied": True})
        decision = result["decisions"][0]
        self.assertEqual(decision["device_id"], device["id"])
        self.assertIn(decision["action"], ("ON", "OFF"))
        self.assertTrue(decision["explanation"])
        self.assertGreater(result["reading"]["posterior"], result["reading"]["prior"])

        history = services.list_decisions(self.conn)
        self.assertEqual(history["total"], 1)
        stored = history["items"][0]
        for key in ("ts", "device_name", "motion", "posterior", "predicted", "action", "explanation"):
            self.assertIn(key, stored)

        summary = analytics.summary(self.conn, tariff=20)
        self.assertEqual(summary["total"]["decisions"], 1)
        self.assertAlmostEqual(summary["total"]["base_kwh"], 0.3)       # 1200 W x 15 min
        report = analytics.report_csv(self.conn)
        self.assertIn("device,,Living room,AC", report)

    def test_data_survives_reconnect(self):
        from backend import services
        room, _ = self.make_home()
        services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 08:00", "motion": False})
        services.update_settings(self.conn, {"tariff_per_kwh": 31.5})
        self.conn.close()
        self.conn = self.db.connect("home")       # like restarting the app
        self.assertEqual(len(services.list_rooms(self.conn)), 1)
        self.assertEqual(services.list_readings(self.conn)["total"], 1)
        self.assertEqual(services.list_decisions(self.conn)["total"], 1)
        self.assertEqual(self.db.get_settings(self.conn)["tariff_per_kwh"], 31.5)

    def test_units_follow_power_and_interval(self):
        from backend import analytics, services
        room, _ = self.make_home(power=1500)
        services.update_settings(self.conn, {"interval_minutes": 30, "tariff_per_kwh": 10})
        services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 08:30", "motion": True})
        decision = services.list_decisions(self.conn)["items"][0]
        self.assertEqual(decision["baseline_energy_wh"], 750.0)       # 1500 W x 0.5 h
        total = analytics.summary(self.conn)["total"]
        self.assertAlmostEqual(total["base_kwh"], 0.75)
        self.assertAlmostEqual(total["base_cost"], 7.5)

    def test_reading_validation(self):
        from backend import services
        room, _ = self.make_home()
        for body in ({"room_id": room["id"], "ts": "2026-11-12 08:07", "motion": True},
                     {"room_id": room["id"], "ts": "12.11.2026 08:00", "motion": True},
                     {"room_id": 999, "ts": "2026-11-12 08:00", "motion": True},
                     {"room_id": room["id"], "ts": "2026-11-12 08:00", "motion": "yes"}):
            with self.assertRaises(services.ValidationError):
                services.add_reading(self.conn, body)
        services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 08:00", "motion": True})
        with self.assertRaises(services.ValidationError):   # duplicate
            services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 08:00", "motion": False})

    def test_manual_mode_and_archive(self):
        from backend import services
        room, device = self.make_home()
        services.control_device(self.conn, device["id"], {"state": "ON"})
        out = services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 03:00", "motion": False})
        self.assertEqual(out["decisions"][0]["mode"], "manual")
        self.assertEqual(out["decisions"][0]["action"], "ON")
        self.assertEqual(services.control_log(self.conn)[0]["action"], "ON")
        services.set_device_archived(self.conn, device["id"], True)
        out = services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 03:15", "motion": False})
        self.assertEqual(out["decisions"], [])
        with self.assertRaises(services.ValidationError):
            services.control_device(self.conn, device["id"], {"state": "OFF"})

    def test_outside_schedule_auto_never_starts(self):
        from backend import services
        room, _ = self.make_home(schedule=[0] * 24)
        out = services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 20:00", "motion": True})
        self.assertEqual(out["decisions"][0]["action"], "OFF")
        self.assertEqual(out["decisions"][0]["baseline_action"], "OFF")

    def test_interval_cannot_change_after_readings(self):
        from backend import services
        room, _ = self.make_home()
        services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 20:00", "motion": True})
        with self.assertRaises(services.ValidationError):
            services.update_settings(self.conn, {"interval_minutes": 30})

    def test_settings_validation(self):
        from backend import services
        for bad in ({"tariff_per_kwh": -1}, {"motion_if_occupied": 0.1}, {"horizon": 2.5},
                    {"unknown": 1}, {"motion_if_occupied": 0.5, "motion_if_empty": 0.5},
                    {"interval_minutes": 7}):
            with self.assertRaises(services.ValidationError, msg=bad):
                services.update_settings(self.conn, bad)

    def test_device_validation_and_room_names(self):
        from backend import services
        room, device = self.make_home()
        with self.assertRaises(services.ValidationError):
            services.create_room(self.conn, {"name": "living ROOM"})   # case-insensitive duplicate
        with self.assertRaises(services.ValidationError):
            services.create_device(self.conn, {"name": "X", "type": "fan", "room_id": room["id"], "power_w": 0})
        with self.assertRaises(services.ValidationError):
            services.update_device(self.conn, device["id"], {"schedule": [1] * 23})
        updated = services.update_device(self.conn, device["id"], {"power_w": 900, "name": "Split AC"})
        self.assertEqual((updated["power_w"], updated["name"]), (900, "Split AC"))

    def test_filter_uses_previous_interval(self):
        from backend import services
        room, _ = self.make_home()
        first = services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 08:00", "motion": True})
        second = services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 08:15", "motion": False})
        self.assertEqual(second["reading"]["prior_source"], "filter")
        self.assertAlmostEqual(second["reading"]["prior"], first["reading"]["predicted"])
        gap = services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 10:00", "motion": False})
        self.assertEqual(gap["reading"]["prior_source"], "default")

    def test_priors_do_not_look_ahead(self):
        from backend import importer, services
        room, _ = self.make_home()
        rows = ["timestamp,room,motion"] + [f"2026-11-13 {h:02d}:{m:02d},Living room,1"
                                            for h in range(24) for m in (0, 15, 30, 45)]
        importer.import_csv(self.conn, "future.csv", "\n".join(rows))
        # A reading for an EARLIER day must not learn from the later day's data.
        out = services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 12:00", "motion": True})
        self.assertEqual(out["reading"]["prior_source"], "default")
        later = services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-14 12:00", "motion": True})
        self.assertEqual(later["reading"]["prior_source"], "hourly")

    def test_comfort_needs_labels(self):
        from backend import analytics, services
        room, _ = self.make_home()
        services.add_reading(self.conn, {"room_id": room["id"], "ts": "2026-11-12 08:00", "motion": False})
        data = analytics.summary(self.conn)
        self.assertIsNone(data["total"]["ai_missed_min"])
        self.assertIn("cannot be evaluated", data["comfort_note"])
        compare = analytics.compare_strategies(self.conn)
        self.assertIsNone(compare["strategies"][0]["missed_min"])
        self.assertNotIn("oracle", [s["policy"] for s in compare["strategies"]])

    def test_period_validation(self):
        from backend import analytics, services
        with self.assertRaises(services.ValidationError):
            analytics.summary(self.conn, date_from="2026-11-10", date_to="2026-11-01")
        with self.assertRaises(services.ValidationError):
            analytics.summary(self.conn, date_from="10.11.2026")


class CsvImportTests(TempDataMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        from backend import services
        services.create_room(self.conn, {"name": "Living room"})
        services.create_room(self.conn, {"name": "Bedroom"})

    def test_example_file_imports(self):
        from backend import importer, services
        result = importer.import_csv(self.conn, "readings_example.csv",
                                     (SAMPLES / "readings_example.csv").read_text(encoding="utf-8"))
        self.assertEqual(result["rows"], 192)
        self.assertEqual(result["labelled"], 144)
        self.assertEqual(services.list_readings(self.conn)["total"], 192)

    def test_bad_file_stores_nothing_and_reports_lines(self):
        from backend import importer, services
        with self.assertRaises(services.ValidationError) as context:
            importer.import_csv(self.conn, "bad.csv",
                                (SAMPLES / "readings_with_errors.csv").read_text(encoding="utf-8"))
        details = "\n".join(context.exception.details)
        for expected in ("Line 3", "Line 4: room 'Kitchen'", "Line 5", "Line 6: motion 'maybe'",
                         "Line 7: occupied '2'", "Line 8: duplicate of line 2"):
            self.assertIn(expected, details)
        self.assertEqual(services.list_readings(self.conn)["total"], 0)

    def test_header_and_format_problems(self):
        from backend import importer, services
        for content in ("", "time,place,move\n2026-11-12 08:00,Bedroom,1", "timestamp,room,motion\n"):
            with self.assertRaises(services.ValidationError):
                importer.import_csv(self.conn, "x.csv", content)

    def test_semicolon_and_bom_and_existing_duplicates(self):
        from backend import importer, services
        text = "﻿timestamp;room;motion;occupied\n2026-11-12 08:00;bedroom;yes;\n2026-11-12 08:15;Bedroom;no;0\n"
        self.assertEqual(importer.import_csv(self.conn, "s.csv", text)["rows"], 2)
        with self.assertRaises(services.ValidationError) as context:
            importer.import_csv(self.conn, "s.csv", text)
        self.assertIn("already stored", context.exception.details[0])


class DemoTests(TempDataMixin, unittest.TestCase):
    def test_demo_is_reproducible_and_separate(self):
        from backend import demo, services
        first = demo.generate_demo(days=2, seed=5)
        conn = self.db.connect("demo")
        try:
            snapshot = [tuple(r) for r in conn.execute("SELECT room_id, ts, motion, occupied FROM readings ORDER BY id")]
            self.assertEqual(len(snapshot), first["readings"])
            self.assertTrue(all(r["source"] == "demo" for r in conn.execute("SELECT source FROM readings")))
        finally:
            conn.close()
        demo.generate_demo(days=2, seed=5)
        conn = self.db.connect("demo")
        try:
            again = [tuple(r) for r in conn.execute("SELECT room_id, ts, motion, occupied FROM readings ORDER BY id")]
        finally:
            conn.close()
        self.assertEqual(snapshot, again)
        self.assertEqual(services.list_readings(self.conn)["total"], 0)   # home untouched

    def test_replay_reproduces_stored_decisions(self):
        from backend import analytics, demo
        demo.generate_demo(days=2, seed=9)
        conn = self.db.connect("demo")
        try:
            stored = analytics.summary(conn)["total"]
            replay = {s["policy"]: s for s in analytics.compare_strategies(conn)["strategies"]}
        finally:
            conn.close()
        self.assertAlmostEqual(replay["mdp"]["kwh"], stored["ai_kwh"])
        self.assertAlmostEqual(replay["schedule"]["kwh"], stored["base_kwh"])
        self.assertEqual(replay["mdp"]["missed_min"], stored["ai_missed_min"])
        self.assertEqual(replay["oracle"]["missed_min"], 0)
        self.assertEqual(replay["oracle"]["wasted_min"], 0)


if __name__ == "__main__":
    unittest.main()
