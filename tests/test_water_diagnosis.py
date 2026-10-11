"""
Unit tests for water_diagnosis.py -- the single source of truth.

Run from the project root:

    python3 tests/test_water_diagnosis.py
    (or) python3 -m unittest discover -s tests
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import water_diagnosis as wd  # noqa: E402


def codes(result):
    return [f["code"] for f in result["findings"]]


def severity_of(result, code):
    for f in result["findings"]:
        if f["code"] == code:
            return f["severity"]
    return None


class ValidationTests(unittest.TestCase):
    def test_valid_reading(self):
        clean, errors = wd.validate_reading(
            {"ph": "7.2", "turbidity": "1.5", "tds": "400", "dissolved_oxygen": "5.5"})
        self.assertEqual(errors, {})
        self.assertEqual(clean["ph"], 7.2)
        self.assertEqual(clean["dissolved_oxygen"], 5.5)

    def test_ph_must_be_0_to_14(self):
        _, errors = wd.validate_reading({"ph": "15", "turbidity": "1", "tds": "400"})
        self.assertEqual(errors.get("ph"), "error.too_high")
        _, errors = wd.validate_reading({"ph": "-1", "turbidity": "1", "tds": "400"})
        self.assertEqual(errors.get("ph"), "error.too_low")

    def test_no_negative_turbidity_or_tds(self):
        _, errors = wd.validate_reading({"ph": "7", "turbidity": "-0.5", "tds": "400"})
        self.assertEqual(errors.get("turbidity"), "error.too_low")
        _, errors = wd.validate_reading({"ph": "7", "turbidity": "1", "tds": "-10"})
        self.assertEqual(errors.get("tds"), "error.too_low")

    def test_tds_max_50000_and_do_max_20(self):
        _, errors = wd.validate_reading({"ph": "7", "turbidity": "1", "tds": "50001"})
        self.assertEqual(errors.get("tds"), "error.too_high")
        _, errors = wd.validate_reading(
            {"ph": "7", "turbidity": "1", "tds": "500", "dissolved_oxygen": "21"})
        self.assertEqual(errors.get("dissolved_oxygen"), "error.too_high")

    def test_do_is_optional(self):
        clean, errors = wd.validate_reading({"ph": "7", "turbidity": "1", "tds": "500"})
        self.assertEqual(errors, {})
        self.assertIsNone(clean["dissolved_oxygen"])

    def test_missing_required_value(self):
        _, errors = wd.validate_reading({"ph": "", "turbidity": "1", "tds": "500"})
        self.assertEqual(errors.get("ph"), "error.required")


class GaugeTests(unittest.TestCase):
    def test_ph_states(self):
        self.assertEqual(wd.ph_state(7.0), "ok")
        self.assertEqual(wd.ph_state(6.2), "watch")
        self.assertEqual(wd.ph_state(5.5), "unsafe")
        self.assertEqual(wd.ph_state(9.5), "unsafe")
        self.assertEqual(wd.ph_state(None), "none")

    def test_turbidity_states(self):
        self.assertEqual(wd.turbidity_state(0.5), "ok")
        self.assertEqual(wd.turbidity_state(3), "watch")
        self.assertEqual(wd.turbidity_state(7), "unsafe")

    def test_tds_states(self):
        self.assertEqual(wd.tds_state(400), "ok")
        self.assertEqual(wd.tds_state(900), "watch")
        self.assertEqual(wd.tds_state(2500), "unsafe")

    def test_do_states_project_rule(self):
        self.assertEqual(wd.do_state(5), "ok")
        self.assertEqual(wd.do_state(3), "watch")
        self.assertEqual(wd.do_state(1), "unsafe")


class SingleParameterTests(unittest.TestCase):
    def test_acidic_ph_alone_is_medium(self):
        r = wd.diagnose(ph=6.1, turbidity=0.5, tds=300)
        self.assertEqual(severity_of(r, "acidic_ph"), "MEDIUM")
        self.assertEqual(r["status"], wd.STATUS_WATCH)

    def test_alkaline_ph_alone_is_medium(self):
        r = wd.diagnose(ph=8.9, turbidity=0.5, tds=300)
        self.assertEqual(severity_of(r, "alkaline_ph"), "MEDIUM")

    def test_cloudy_water_is_medium(self):
        r = wd.diagnose(ph=7.2, turbidity=7.0, tds=300)
        self.assertEqual(severity_of(r, "cloudy"), "MEDIUM")

    def test_slightly_cloudy_is_low(self):
        r = wd.diagnose(ph=7.2, turbidity=2.0, tds=300)
        self.assertEqual(severity_of(r, "slightly_cloudy"), "LOW")
        self.assertEqual(r["status"], wd.STATUS_WATCH)

    def test_low_do_warning_and_very_low(self):
        self.assertEqual(severity_of(wd.diagnose(ph=7, turbidity=1, tds=300,
                                                 dissolved_oxygen=3), "low_do"), "MEDIUM")
        self.assertEqual(severity_of(wd.diagnose(ph=7, turbidity=1, tds=300,
                                                 dissolved_oxygen=1), "very_low_do"), "HIGH")

    def test_high_tds_levels(self):
        self.assertEqual(severity_of(wd.diagnose(ph=7, turbidity=1, tds=1500), "high_tds"),
                         "MEDIUM")
        self.assertEqual(severity_of(wd.diagnose(ph=7, turbidity=1, tds=2500), "very_high_tds"),
                         "HIGH")

    def test_all_normal_is_ok_but_never_claims_safe(self):
        r = wd.diagnose(ph=7.2, turbidity=0.4, tds=250, dissolved_oxygen=6)
        self.assertEqual(r["status"], wd.STATUS_OK)
        self.assertIn("nothing_found", codes(r))
        self.assertTrue(r["disclaimer"])


class CombinedRuleTests(unittest.TestCase):
    def test_sewage_is_critical(self):
        r = wd.diagnose(ph=7.0, turbidity=8, tds=400, dissolved_oxygen=3,
                        reports=["bad_smell"])
        self.assertEqual(severity_of(r, "sewage"), "CRITICAL")
        self.assertEqual(r["status"], wd.STATUS_UNSAFE)
        self.assertEqual(r["findings"][0]["code"], "sewage")
        self.assertEqual(r["findings"][0]["department"], "health")

    def test_sewage_needs_all_three_signals(self):
        # no smell -> not the sewage rule
        self.assertNotIn("sewage", codes(wd.diagnose(ph=7, turbidity=8, tds=400,
                                                     dissolved_oxygen=3)))
        # no low oxygen -> not the sewage rule
        self.assertNotIn("sewage", codes(wd.diagnose(ph=7, turbidity=8, tds=400,
                                                     dissolved_oxygen=6,
                                                     reports=["bad_smell"])))

    def test_low_ph_high_tds_is_high_industrial(self):
        r = wd.diagnose(ph=5.5, turbidity=1, tds=800)
        self.assertEqual(severity_of(r, "acid_industrial"), "HIGH")
        self.assertEqual(r["findings"][0]["department"], "tpcb")
        self.assertEqual(r["status"], wd.STATUS_UNSAFE)

    def test_low_ph_soft_water_is_medium(self):
        r = wd.diagnose(ph=5.8, turbidity=1, tds=60)
        self.assertEqual(severity_of(r, "corrosive_soft"), "MEDIUM")
        self.assertEqual(r["status"], wd.STATUS_WATCH)

    def test_low_ph_turbid_is_high_rusty_pipes(self):
        r = wd.diagnose(ph=6.0, turbidity=7, tds=300)
        self.assertEqual(severity_of(r, "rusty_pipes"), "HIGH")
        self.assertEqual(r["status"], wd.STATUS_UNSAFE)

    def test_high_ph_high_tds_normal_turbidity_is_medium(self):
        r = wd.diagnose(ph=8.8, turbidity=1, tds=700)
        self.assertEqual(severity_of(r, "hard_alkaline"), "MEDIUM")

    def test_high_ph_turbid_is_medium_algae(self):
        r = wd.diagnose(ph=8.8, turbidity=7, tds=300)
        self.assertEqual(severity_of(r, "algae_lime"), "MEDIUM")

    def test_normal_ph_high_tds_is_low_salinity(self):
        r = wd.diagnose(ph=7.2, turbidity=0.5, tds=800)
        self.assertEqual(severity_of(r, "salinity"), "LOW")
        self.assertEqual(r["status"], wd.STATUS_WATCH)

    def test_salty_taste_plus_high_tds_is_high(self):
        r = wd.diagnose(ph=7.2, turbidity=0.5, tds=800, reports=["salty_taste"])
        self.assertEqual(severity_of(r, "salty_taste"), "HIGH")
        self.assertEqual(r["findings"][0]["department"], "tpcb")
        self.assertEqual(r["status"], wd.STATUS_UNSAFE)

    def test_normal_readings_with_no_supply_is_medium_distribution_fault(self):
        r = wd.diagnose(ph=7.1, turbidity=0.5, tds=300, reports=["no_supply"])
        self.assertEqual(severity_of(r, "distribution_fault"), "MEDIUM")

    def test_distribution_fault_not_raised_when_readings_are_off(self):
        r = wd.diagnose(ph=6.1, turbidity=0.5, tds=300, reports=["no_supply"])
        self.assertNotIn("distribution_fault", codes(r))

    def test_findings_sorted_by_severity(self):
        r = wd.diagnose(ph=7.0, turbidity=8, tds=2500, dissolved_oxygen=3,
                        reports=["bad_smell"])
        order = [wd.SEVERITY_ORDER[f["severity"]] for f in r["findings"]]
        self.assertEqual(order, sorted(order, reverse=True))


class IllnessTests(unittest.TestCase):
    def test_illness_flag_is_reported(self):
        r = wd.diagnose(ph=7, turbidity=1, tds=300, ill=True)
        self.assertTrue(r["illness_advice"])
        r2 = wd.diagnose(ph=7, turbidity=1, tds=300, ill=False)
        self.assertFalse(r2["illness_advice"])


class FindingMetaTests(unittest.TestCase):
    def test_every_code_has_actions_and_a_department(self):
        for code in wd.CODE_PROBES:
            meta = wd.finding_meta(code)
            self.assertIn(meta["severity"], wd.SEVERITY_ORDER, code)
            self.assertIn(meta["department"], ["engineer", "health", "tpcb",
                                               "grievance", "commissioner",
                                               "works", "twad", "zone_office"], code)
            self.assertTrue(meta["quick_actions"], code)

    def test_every_finding_code_is_producible(self):
        for code in wd.CODE_PROBES:
            self.assertIn(code, wd.QUICK_ACTIONS, code)
            self.assertIn(code, wd.CAPITAL_WORKS, code)


class HotspotTests(unittest.TestCase):
    def _reading(self, ward="Ward 46", zone="Katpadi", code="sewage",
                 severity="MEDIUM", days_ago=1, status="Submitted"):
        return {
            "ward": ward, "zone": zone, "severity": severity, "status": status,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=days_ago))
                           .strftime("%Y-%m-%d %H:%M:%S"),
            "codes": [code],
        }

    def test_three_reports_in_seven_days_make_a_hotspot(self):
        rows = [self._reading(days_ago=d) for d in (1, 2, 6)]
        hotspots = wd.build_hotspots(rows)
        self.assertEqual(len(hotspots), 1)
        h = hotspots[0]
        self.assertEqual(h["ward"], "Ward 46")
        self.assertEqual(h["report_count"], 3)
        self.assertTrue(h["needs_lab_confirmation"])

    def test_two_reports_are_not_enough(self):
        rows = [self._reading(days_ago=d) for d in (1, 2)]
        self.assertEqual(wd.build_hotspots(rows), [])

    def test_reports_older_than_seven_days_do_not_count(self):
        rows = [self._reading(days_ago=d) for d in (1, 2, 12)]
        self.assertEqual(wd.build_hotspots(rows), [])

    def test_single_critical_is_a_hotspot(self):
        rows = [self._reading(days_ago=1, severity="CRITICAL", code="sewage")]
        hotspots = wd.build_hotspots(rows)
        self.assertEqual(len(hotspots), 1)
        self.assertEqual(hotspots[0]["severity"], "CRITICAL")

    def test_same_diagnosis_same_ward_required(self):
        rows = [self._reading(ward="Ward 46", days_ago=1),
                self._reading(ward="Ward 47", days_ago=1),
                self._reading(ward="Ward 48", days_ago=1)]
        self.assertEqual(wd.build_hotspots(rows), [])

    def test_ranking_severity_then_reports_then_duration(self):
        now = datetime.now(timezone.utc)
        rows = [
            self._reading(ward="Ward 50", code="acidic_ph", severity="MEDIUM",
                          days_ago=1),
            self._reading(ward="Ward 51", code="acidic_ph", severity="MEDIUM",
                          days_ago=1),
            self._reading(ward="Ward 52", code="acidic_ph", severity="MEDIUM",
                          days_ago=1),
            self._reading(ward="Ward 53", code="sewage", severity="CRITICAL",
                          days_ago=1),
        ]
        hotspots = wd.build_hotspots(rows, now=now)
        self.assertEqual(hotspots[0]["ward"], "Ward 53")

    def test_quick_actions_come_before_capital_works(self):
        rows = [self._reading(days_ago=d) for d in (1, 2, 3)]
        h = wd.build_hotspots(rows)[0]
        self.assertTrue(h["quick_actions"])
        self.assertTrue(h["capital_works"])
        self.assertNotEqual(h["quick_actions"], h["capital_works"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
