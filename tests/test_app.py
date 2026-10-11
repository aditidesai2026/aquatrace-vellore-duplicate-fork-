"""
Smoke tests for the Flask app: every page renders, the reporting API works,
the officials login/status/export flows work, and privacy rules hold.

Run from the project root:  python3 tests/test_app.py
"""

import json
import os
import sys
import tempfile
import unittest

# Use an isolated database before app.py is imported.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
os.environ["AQUATRACE_DB"] = _TMP.name

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as aquatrace  # noqa: E402
import config  # noqa: E402
import water_diagnosis as wd  # noqa: E402


@aquatrace.app.route("/__boom")
def _boom():
    """Test-only route used to check the friendly 500 page."""
    raise RuntimeError("boom")


class PageTests(unittest.TestCase):
    def setUp(self):
        aquatrace.app.config["TESTING"] = True
        self.client = aquatrace.app.test_client()

    def _get(self, path, expect=200):
        r = self.client.get(path)
        self.assertEqual(r.status_code, expect, path)
        return r

    def test_home(self):
        body = self._get("/").get_data(as_text=True)
        self.assertIn("Check my water", body)
        self.assertIn("Serving Vellore, starting with Katpadi", body)
        self.assertIn("tel:9280097911", body)          # tap-to-call
        self.assertIn("mailto:iccc.vellore@gmail.com", body)  # tap-to-email
        self.assertIn("Last checked", body)

    def test_all_public_pages_render(self):
        for path in ("/", "/check", "/map", "/charts", "/learn", "/contacts",
                     "/officials", "/does-not-exist"):
            expected = 404 if path == "/does-not-exist" else 200
            self._get(path, expected)

    def test_every_template_exists(self):
        import jinja2
        for name in ("500.html", "404.html", "base.html", "result.html",
                     "officials.html", "officials_print.html"):
            try:
                aquatrace.app.jinja_env.get_template(name)
            except jinja2.TemplateNotFound:
                self.fail("missing template: %s" % name)

    def test_500_page_is_friendly(self):
        aquatrace.app.config["PROPAGATE_EXCEPTIONS"] = False
        try:
            r = self.client.get("/__boom")
            self.assertEqual(r.status_code, 500)
            body = r.get_data(as_text=True)
            self.assertIn("Something broke", body)
            self.assertIn("Please go back and try again", body)
        finally:
            aquatrace.app.config["PROPAGATE_EXCEPTIONS"] = None

    def test_wizard_has_six_steps_and_validation_attrs(self):
        body = self._get("/check").get_data(as_text=True)
        self.assertEqual(body.count('class="wizard-step"'), 6)
        for field in ("ph", "turbidity", "tds", "dissolved_oxygen"):
            self.assertIn('name="%s"' % field, body)
        self.assertIn('name="zone"', body)
        self.assertIn("Katpadi", body)          # default zone
        self.assertIn("Ward 60", body)          # 60 wards exist

    def test_learn_and_contacts_pages(self):
        learn = self._get("/learn").get_data(as_text=True)
        self.assertIn("6.5", learn)
        self.assertIn("BIS IS 10500:2012", learn)
        contacts = self._get("/contacts").get_data(as_text=True)
        self.assertIn("7397389319", contacts)   # City Engineer
        self.assertIn("9280097516", contacts)   # City Health Officer
        self.assertIn("0416-2211224", contacts) # TWAD Katpadi
        self.assertIn("to confirm", contacts)   # placeholder contacts flagged


class ReadingApiTests(unittest.TestCase):
    def setUp(self):
        aquatrace.app.config["TESTING"] = True
        # keep test uploads out of the project's static/uploads folder
        self._uploads = tempfile.mkdtemp(prefix="aq-uploads-")
        self._prev_uploads = aquatrace.app.config["UPLOAD_FOLDER"]
        aquatrace.app.config["UPLOAD_FOLDER"] = self._uploads
        self.client = aquatrace.app.test_client()

    def tearDown(self):
        aquatrace.app.config["UPLOAD_FOLDER"] = self._prev_uploads
        import shutil
        shutil.rmtree(self._uploads, ignore_errors=True)

    def _post(self, payload):
        return self.client.post("/api/readings", json=payload)

    def test_create_and_render_result(self):
        r = self._post({
            "ph": 5.5, "turbidity": 1.0, "tds": 800,
            "zone": "Katpadi", "ward": "Ward 46",
            "reports": ["salty_taste"], "ill": True,
            "first_name": "Test", "note": "from the garden tap",
        })
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        data = r.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["status"], "UNSAFE")

        page = self.client.get(data["redirect"])
        self.assertEqual(page.status_code, 200)
        body = page.get_data(as_text=True)
        self.assertIn("Report this to VCMC", body)
        self.assertIn("does NOT prove water is safe to drink", body)
        self.assertIn("Please see a doctor or visit the nearest hospital", body)
        self.assertIn("Ward 46", body)
        # department mapping: industrial discharge -> Pollution Control Board
        self.assertIn("Pollution Control Board", body)

    def test_validation_rejects_bad_values(self):
        r = self._post({"ph": 15, "turbidity": 1, "tds": 400,
                        "zone": "Katpadi", "ward": "Ward 46"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["errors"].get("ph"), "error.too_high")

    def test_optional_do_can_be_skipped(self):
        r = self._post({"ph": 7.2, "turbidity": 0.5, "tds": 300,
                        "zone": "Katpadi", "ward": "Ward 46"})
        self.assertEqual(r.status_code, 200)
        reading = aquatrace.database.get_reading(r.get_json()["id"])
        self.assertIsNone(reading["dissolved_oxygen"])

    def test_outside_vellore_is_rejected(self):
        r = self._post({"ph": 7.2, "turbidity": 0.5, "tds": 300,
                        "zone": "Katpadi", "ward": "Ward 46",
                        "latitude": 13.0827, "longitude": 80.2707})  # Chennai
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.get_json().get("outside_vellore"))

    def test_gps_resolves_to_nearest_ward_and_stores_ward_marker_only(self):
        r = self._post({"ph": 7.2, "turbidity": 0.5, "tds": 300,
                        "zone": "Katpadi", "ward": "Ward 46",
                        "latitude": 12.9700, "longitude": 79.1460})
        self.assertEqual(r.status_code, 200)
        reading = aquatrace.database.get_reading(r.get_json()["id"])
        expected = config.ward_centroid(reading["zone"], reading["ward"])
        self.assertEqual((reading["latitude"], reading["longitude"]), expected)
        self.assertIn(reading["ward"], config.wards_for_zone(reading["zone"]))

    def test_repeat_form_fields_collect_all_chips(self):
        r = self.client.post("/api/readings", data={
            "ph": "7.2", "turbidity": "0.5", "tds": "300",
            "zone": "Katpadi", "ward": "Ward 46",
            "reports": ["bad_smell", "cloudy_water"],
        })
        self.assertEqual(r.status_code, 200)
        reading = aquatrace.database.get_reading(r.get_json()["id"])
        self.assertEqual(sorted(reading["reports"]), ["bad_smell", "cloudy_water"])

    def test_validate_endpoint(self):
        r = self.client.post("/api/validate", json={"ph": "7", "turbidity": "-1",
                                                    "tds": "400"})
        data = r.get_json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["errors"]["turbidity"], "error.too_low")

    def test_optional_photo_is_saved_and_rejected_for_non_images(self):
        import io
        # a real image upload
        r = self.client.post("/api/readings", data={
            "ph": "7.2", "turbidity": "0.5", "tds": "300",
            "zone": "Katpadi", "ward": "Ward 46",
            "photo": (io.BytesIO(b"\x89PNG\r\n\x1a\n000"), "tap.png"),
        }, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        reading = aquatrace.database.get_reading(r.get_json()["id"])
        self.assertTrue(reading["photo"].endswith(".png"))
        self.assertEqual(self.client.get("/uploads/" + reading["photo"]).status_code, 200)

        # a non-image is silently ignored, never stored
        r = self.client.post("/api/readings", data={
            "ph": "7.2", "turbidity": "0.5", "tds": "300",
            "zone": "Katpadi", "ward": "Ward 46",
            "photo": (io.BytesIO(b"rm -rf /"), "evil.sh"),
        }, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        reading = aquatrace.database.get_reading(r.get_json()["id"])
        self.assertEqual(reading["photo"], "")

    def test_ok_result_has_disclaimer_but_no_report_card(self):
        r = self._post({"ph": 7.2, "turbidity": 0.4, "tds": 250,
                        "dissolved_oxygen": 6, "zone": "Katpadi",
                        "ward": "Ward 52"})
        self.assertEqual(r.get_json()["status"], "OK")
        body = self.client.get(r.get_json()["redirect"]).get_data(as_text=True)
        self.assertIn("does NOT prove water is safe to drink", body)
        self.assertNotIn("Report this to VCMC", body)
        self.assertNotIn("Please see a doctor", body)


class ApiTests(unittest.TestCase):
    def setUp(self):
        aquatrace.app.config["TESTING"] = True
        self.client = aquatrace.app.test_client()

    def test_limits_come_from_diagnosis_module(self):
        data = self.client.get("/api/limits").get_json()
        self.assertEqual(data["ph"]["accept_min"], wd.PH_ACCEPTABLE_MIN)
        self.assertEqual(data["turbidity"]["problem"], wd.TURBIDITY_PROBLEM)
        self.assertEqual(data["tds"]["permissible"], wd.TDS_PERMISSIBLE)
        self.assertEqual(data["dissolved_oxygen"]["warning"], wd.DO_WARNING)

    def test_areas_lists_four_zones_and_sixty_wards(self):
        data = self.client.get("/api/areas").get_json()
        self.assertEqual(len(data["zones"]), 4)
        self.assertEqual(sum(len(v) for v in data["wards_by_zone"].values()), 60)
        self.assertEqual(data["default_zone"], "Katpadi")

    def test_stats_and_map_and_charts(self):
        stats = self.client.get("/api/stats").get_json()
        self.assertIn("today", stats)
        m = self.client.get("/api/map").get_json()
        self.assertIn("wards", m)
        c = self.client.get("/api/charts?group=zone").get_json()
        for key in ("avg", "series", "hist", "severity", "problems",
                    "day_zone", "ward_matrix", "scatter"):
            self.assertIn(key, c)

    def test_demo_load_and_remove(self):
        r = self.client.post("/api/demo", json={"action": "load"})
        self.assertEqual(r.get_json()["action"], "load")
        self.assertGreater(r.get_json()["count"], 50)

        stats = self.client.get("/api/stats").get_json()
        self.assertGreater(stats["total"], 50)

        # hotspots must appear from the deliberate Katpadi cluster
        hot = self.client.get("/api/hotspots").get_json()["hotspots"]
        self.assertTrue(hot)
        self.assertTrue(all(h["needs_lab_confirmation"] for h in hot))

        # every public map pin is a ward-level centroid, never a raw GPS point
        for ward in self.client.get("/api/map").get_json()["wards"]:
            self.assertEqual((ward["lat"], ward["lon"]),
                             config.ward_centroid(ward["zone"], ward["ward"]))

        r = self.client.post("/api/demo", json={"action": "remove"})
        self.assertEqual(r.get_json()["action"], "remove")
        self.assertEqual(self.client.get("/api/stats").get_json()["total"], 0)

    def test_unknown_demo_action(self):
        r = self.client.post("/api/demo", json={"action": "nope"})
        self.assertEqual(r.status_code, 400)


class OfficialsTests(unittest.TestCase):
    def setUp(self):
        aquatrace.app.config["TESTING"] = True
        self.client = aquatrace.app.test_client()

    def test_dashboard_requires_password(self):
        r = self.client.get("/officials/dashboard")
        self.assertEqual(r.status_code, 403)

    def test_login_dashboard_status_and_exports(self):
        # wrong password
        r = self.client.post("/officials/login", data={"password": "wrong"})
        self.assertEqual(r.status_code, 401)

        # right password
        r = self.client.post("/officials/login", data={"password": config.OFFICIALS_PASSWORD},
                             follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Officials dashboard", r.get_data(as_text=True))

        # load demo data, then move a hotspot through the workflow
        self.client.post("/api/demo", json={"action": "load"})
        hot = self.client.get("/api/hotspots").get_json()["hotspots"]
        self.assertTrue(hot)
        first = hot[0]

        r = self.client.post("/officials/status", json={
            "ward": first["ward"], "code": first["code"], "status": "In progress"})
        self.assertEqual(r.get_json()["ok"], True)

        # residents see the new status on their report
        detail = self.client.get("/api/hotspots").get_json()["hotspots"][0]
        self.assertEqual(detail["status"], "In progress")

        # bad status is refused
        r = self.client.post("/officials/status", json={
            "ward": first["ward"], "code": first["code"], "status": "Sorted"})
        self.assertEqual(r.status_code, 400)

        # CSV weekly priority list
        r = self.client.get("/officials/export.csv")
        self.assertEqual(r.status_code, 200)
        csv_text = r.get_data(as_text=True)
        self.assertIn("Needs lab confirmation", csv_text)
        self.assertIn(first["ward"], csv_text)

        # printable PDF view
        r = self.client.get("/officials/print")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Vellore water problems", r.get_data(as_text=True))

    def test_logout(self):
        self.client.post("/officials/login", data={"password": config.OFFICIALS_PASSWORD})
        self.client.post("/officials/logout")
        self.assertEqual(self.client.get("/officials/dashboard").status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=1)
