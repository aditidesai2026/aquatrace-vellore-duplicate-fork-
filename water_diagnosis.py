"""
water_diagnosis.py -- AquaTrace water quality diagnosis engine.
===============================================================

This module is the SINGLE SOURCE OF TRUTH for every judgement AquaTrace makes.
Nothing else in the app is allowed to decide whether water is "OK", "Watch" or
"Unsafe": templates, APIs, the map, the charts and the officials dashboard all
call ``diagnose()`` (or read the result it produced) and display what it says.

Reference limits used below
---------------------------
* pH            : acceptable 6.5 - 8.5
                  -- BIS IS 10500:2012 (Indian Standard for Drinking Water
                     Specifications, acceptable range) and WHO Drinking Water
                     Guidelines (pH 6.5-8.5 typical operational range).
* Turbidity     : acceptable up to 1 NTU, problem above 5 NTU
                  -- BIS IS 10500:2012 acceptable limit is 1 NTU (max 5 NTU
                     allowable in the absence of alternative source).
* TDS           : acceptable up to 500 mg/L, tastes bad above 1000 mg/L (WHO),
                  permissible up to 2000 mg/L (BIS), very high above 2000 mg/L.
                  -- BIS IS 10500:2012 acceptable 500 / permissible 2000 mg/L;
                     WHO notes taste complaints above about 1000 mg/L.
* Dissolved O2  : below 4 mg/L = warning, below 2 mg/L = very low.
                  -- PROJECT RULE for AquaTrace. This is NOT a drinking water
                     standard. Low dissolved oxygen indicates stagnant or
                     organically loaded water and is used only as a hint.

Nothing here tests for bacteria, nitrate, fluoride, arsenic or heavy metals.
Every result therefore carries the indicative-only disclaimer.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# 1. Limits (see module docstring for the citations)
# ---------------------------------------------------------------------------

PH_ACCEPTABLE_MIN = 6.5
PH_ACCEPTABLE_MAX = 8.5
# "edge" bands used only for the live colour gauge (green / amber / red)
PH_WATCH_MIN = 6.0
PH_WATCH_MAX = 9.0
PH_INPUT_MIN = 0.0
PH_INPUT_MAX = 14.0

TURBIDITY_ACCEPTABLE = 1.0   # NTU, BIS acceptable
TURBIDITY_PROBLEM = 5.0      # NTU, BIS: not acceptable above this

TDS_ACCEPTABLE = 500.0       # mg/L, BIS/WHO acceptable
TDS_TASTE = 1000.0           # mg/L, WHO taste threshold
TDS_PERMISSIBLE = 2000.0     # mg/L, BIS permissible
TDS_INPUT_MAX = 50000.0      # input sanity cap

DO_WARNING = 4.0             # mg/L, project rule
DO_VERY_LOW = 2.0            # mg/L, project rule
DO_INPUT_MAX = 20.0          # input sanity cap

# Overall status thresholds are derived from finding severities.
STATUS_OK = "OK"
STATUS_WATCH = "WATCH"
STATUS_UNSAFE = "UNSAFE"

SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}

# Recognised "What have you noticed?" chips.
REPORT_CHIPS = (
    "salty_taste",
    "bad_smell",
    "cloudy_water",
    "strange_colour",
    "no_supply",
    "low_pressure",
    "leak",
)

STATUSES = ("Submitted", "Verified", "In progress", "Resolved")

# A hotspot needs 3+ submissions with the same diagnosis in the same ward
# within this many days, or any single CRITICAL submission.
HOTSPOT_WINDOW_DAYS = 7
HOTSPOT_MIN_REPORTS = 3


# ---------------------------------------------------------------------------
# 2. Validation -- used by the wizard (live) and by the API
# ---------------------------------------------------------------------------

def _num(value, name, errors, required, lo, hi):
    """Coerce a value to float and range-check it. Returns float or None."""
    if value is None or value == "":
        if required:
            errors[name] = "error.required"
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        errors[name] = "error.not_a_number"
        return None
    if math.isnan(v):
        errors[name] = "error.not_a_number"
        return None
    if v < lo:
        errors[name] = "error.too_low"
        return None
    if v > hi:
        errors[name] = "error.too_high"
        return None
    return v


def validate_reading(payload):
    """Validate a raw submission.

    Rules (from the AquaTrace brief):
      * pH 0 to 14 (required)
      * turbidity not negative (required)
      * TDS not negative, max 50000 (required)
      * dissolved oxygen not negative, max 20 (optional -- may be skipped)

    Returns ``(clean, errors)`` where ``clean`` holds floats (``None`` when the
    optional value was skipped) and ``errors`` maps field -> i18n message key.
    """
    payload = payload or {}
    errors = {}
    ph = _num(payload.get("ph"), "ph", errors, True, PH_INPUT_MIN, PH_INPUT_MAX)
    turbidity = _num(payload.get("turbidity"), "turbidity", errors, True, 0.0, 1e6)
    tds = _num(payload.get("tds"), "tds", errors, True, 0.0, TDS_INPUT_MAX)
    do = _num(payload.get("dissolved_oxygen"), "dissolved_oxygen", errors, False, 0.0, DO_INPUT_MAX)

    clean = {
        "ph": ph,
        "turbidity": turbidity,
        "tds": tds,
        "dissolved_oxygen": do,
    }
    return clean, errors


# ---------------------------------------------------------------------------
# 3. Per-parameter colour gauge (green = acceptable, amber = watch, red = unsafe)
# ---------------------------------------------------------------------------

def ph_state(ph):
    if ph is None:
        return "none"
    if PH_ACCEPTABLE_MIN <= ph <= PH_ACCEPTABLE_MAX:
        return "ok"
    if PH_WATCH_MIN <= ph <= PH_WATCH_MAX:
        return "watch"
    return "unsafe"


def turbidity_state(turbidity):
    if turbidity is None:
        return "none"
    if turbidity <= TURBIDITY_ACCEPTABLE:
        return "ok"
    if turbidity <= TURBIDITY_PROBLEM:
        return "watch"
    return "unsafe"


def tds_state(tds):
    if tds is None:
        return "none"
    if tds <= TDS_ACCEPTABLE:
        return "ok"
    if tds <= TDS_PERMISSIBLE:
        return "watch"
    return "unsafe"


def do_state(do):
    """Dissolved oxygen: project rule, not a drinking water standard."""
    if do is None:
        return "none"
    if do >= DO_WARNING:
        return "ok"
    if do >= DO_VERY_LOW:
        return "watch"
    return "unsafe"


def parameter_states(ph=None, turbidity=None, tds=None, dissolved_oxygen=None):
    return {
        "ph": ph_state(ph),
        "turbidity": turbidity_state(turbidity),
        "tds": tds_state(tds),
        "dissolved_oxygen": do_state(dissolved_oxygen),
    }


# ---------------------------------------------------------------------------
# 4. Diagnosis rules
# ---------------------------------------------------------------------------

def _f(code, severity, department, also=(), **values):
    return {
        "code": code,
        "severity": severity,
        "department": department,
        "also": list(also),
        "values": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in values.items()},
    }


def diagnose(ph=None, turbidity=None, tds=None, dissolved_oxygen=None,
             reports=None, ill=False):
    """Turn raw readings + what the resident noticed into findings.

    Returns a dict::

        {
          "status": "OK" | "WATCH" | "UNSAFE",
          "findings": [ {code, severity, department, also, values}, ... ],
          "gauges": {parameter: "ok"|"watch"|"unsafe"|"none"},
          "illness_advice": bool,
        }

    Findings are returned already sorted by severity (worst first).
    ``code`` is an i18n key stem: the UI shows ``f.<code>.title`` /
    ``f.<code>.desc`` / ``f.<code>.action`` in the active language.
    """
    reports = set(reports or [])
    findings = []

    pH = ph
    # pH categories used by the combination rules.
    low_ph = pH is not None and pH < PH_ACCEPTABLE_MIN
    high_ph = pH is not None and pH > PH_ACCEPTABLE_MAX
    normal_ph = pH is not None and not low_ph and not high_ph

    turbidity_high = turbidity is not None and turbidity > TURBIDITY_PROBLEM
    turbidity_normal = turbidity is None or turbidity <= TURBIDITY_PROBLEM

    tds_high = tds is not None and tds > TDS_ACCEPTABLE
    tds_very_high = tds is not None and tds > TDS_PERMISSIBLE
    tds_soft = tds is not None and tds < 100.0

    do_low = dissolved_oxygen is not None and dissolved_oxygen < DO_WARNING
    do_very_low = dissolved_oxygen is not None and dissolved_oxygen < DO_VERY_LOW

    ph_consumed = False     # a combination rule already explained the pH
    tds_consumed = False    # a combination rule already explained the TDS
    turbidity_consumed = False
    do_consumed = False

    # --- Combination rules ------------------------------------------------
    # Turbidity > 5 + dissolved oxygen < 4 + smell reported = likely sewage.
    if turbidity_high and do_low and "bad_smell" in reports:
        findings.append(_f("sewage", "CRITICAL", "health", also=["engineer"],
                           turbidity=turbidity, do=dissolved_oxygen))
        ph_consumed = tds_consumed = turbidity_consumed = do_consumed = True

    # Low pH + TDS above 500: acidic industrial or mine discharge, or
    # corrosion releasing metals (HIGH).
    if low_ph and tds_high:
        findings.append(_f("acid_industrial", "HIGH", "tpcb", also=["engineer"],
                           ph=pH, tds=tds))
        ph_consumed = tds_consumed = True

    # Low pH + TDS below 100: soft, poorly buffered, corrosive water (MEDIUM).
    if low_ph and tds_soft:
        findings.append(_f("corrosive_soft", "MEDIUM", "engineer", ph=pH, tds=tds))
        ph_consumed = tds_consumed = True

    # Low pH + turbidity above 5: rusty corroded pipes or organic decay (HIGH).
    if low_ph and turbidity_high:
        findings.append(_f("rusty_pipes", "HIGH", "engineer",
                           ph=pH, turbidity=turbidity))
        ph_consumed = turbidity_consumed = True

    # High pH + TDS above 500 + normal turbidity: hard carbonate-rich water or
    # alkaline discharge (MEDIUM).
    if high_ph and tds_high and turbidity_normal:
        findings.append(_f("hard_alkaline", "MEDIUM", "engineer", also=["tpcb"],
                           ph=pH, tds=tds))
        ph_consumed = tds_consumed = True

    # High pH + turbidity above 5: algae / lime / construction runoff.
    # Chlorine works less well here (MEDIUM).
    if high_ph and turbidity_high:
        findings.append(_f("algae_lime", "MEDIUM", "engineer", also=["health"],
                           ph=pH, turbidity=turbidity))
        ph_consumed = turbidity_consumed = True

    # Normal pH + TDS above 500: neutral salts (salinity). pH alone misses it (LOW).
    if normal_ph and tds_high:
        findings.append(_f("salinity", "LOW", "engineer", tds=tds))
        tds_consumed = True

    # Salty taste + TDS above 500: salinity or industrial discharge (HIGH).
    if "salty_taste" in reports and tds_high:
        findings.append(_f("salty_taste", "HIGH", "tpcb", also=["engineer"],
                           tds=tds))
        tds_consumed = True

    # --- Single-parameter findings ---------------------------------------
    if low_ph and not ph_consumed:
        findings.append(_f("acidic_ph", "MEDIUM", "engineer", ph=pH))
    if high_ph and not ph_consumed:
        findings.append(_f("alkaline_ph", "MEDIUM", "engineer", ph=pH))

    if turbidity is not None and not turbidity_consumed:
        if turbidity > TURBIDITY_PROBLEM:
            findings.append(_f("cloudy", "MEDIUM", "engineer",
                               turbidity=turbidity))
        elif turbidity > TURBIDITY_ACCEPTABLE:
            findings.append(_f("slightly_cloudy", "LOW", "engineer",
                               turbidity=turbidity))

    if tds is not None and not any(
        f["code"] in ("acid_industrial", "salty_taste") for f in findings
    ):
        if tds_very_high:
            findings.append(_f("very_high_tds", "HIGH", "engineer", tds=tds))
        elif tds > TDS_TASTE:
            findings.append(_f("high_tds", "MEDIUM", "engineer", tds=tds))

    if do_low and not do_consumed:
        if do_very_low:
            findings.append(_f("very_low_do", "HIGH", "engineer",
                               also=["health"], do=dissolved_oxygen))
        else:
            findings.append(_f("low_do", "MEDIUM", "engineer",
                               also=["health"], do=dissolved_oxygen))

    # --- Distribution fault: all readings normal but supply problems -------
    readings_clean = (
        normal_ph
        and turbidity is not None and turbidity <= TURBIDITY_ACCEPTABLE
        and tds is not None and tds <= TDS_ACCEPTABLE
        and (dissolved_oxygen is None or dissolved_oxygen >= DO_WARNING)
    )
    supply_reports = reports & {"no_supply", "low_pressure", "leak"}
    if readings_clean and supply_reports and not findings:
        findings.append(_f("distribution_fault", "MEDIUM", "engineer",
                           issues=",".join(sorted(supply_reports))))

    # --- Nothing found: say so, but never say the water is safe -----------
    if not findings:
        findings.append(_f("nothing_found", "NONE", "grievance"))

    findings.sort(key=lambda f: -SEVERITY_ORDER[f["severity"]])

    status = status_from_findings(findings)

    return {
        "status": status,
        "findings": findings,
        "gauges": parameter_states(pH, turbidity, tds, dissolved_oxygen),
        "illness_advice": bool(ill),
        # Always true: this is indicative and never proof of safe drinking water.
        "disclaimer": True,
    }


def status_from_findings(findings):
    """CRITICAL/HIGH -> UNSAFE, MEDIUM/LOW -> WATCH, nothing else -> OK."""
    best = max((SEVERITY_ORDER.get(f.get("severity"), 0) for f in findings),
               default=0)
    if best >= SEVERITY_ORDER["HIGH"]:
        return STATUS_UNSAFE
    if best >= SEVERITY_ORDER["LOW"]:
        return STATUS_WATCH
    return STATUS_OK


# ---------------------------------------------------------------------------
# 5. Actions: cheap fixes first, capital works later
# ---------------------------------------------------------------------------

# Quick, low-cost actions suggested before any capital work.
QUICK_ACTIONS = {
    "sewage": ["act.stop_drinking", "act.boil_or_chlorinate", "act.lab_test", "act.advisory"],
    "acid_industrial": ["act.lab_test", "act.flush_lines", "act.report_discharge"],
    "corrosive_soft": ["act.flush_lines", "act.avoid_metal_vessels", "act.lab_test"],
    "rusty_pipes": ["act.flush_lines", "act.clean_tank", "act.lab_test"],
    "hard_alkaline": ["act.flush_lines", "act.lab_test"],
    "algae_lime": ["act.flush_lines", "act.clean_tank", "act.chlorine_note", "act.lab_test"],
    "salinity": ["act.lab_test", "act.try_alternate_source"],
    "salty_taste": ["act.lab_test", "act.try_alternate_source"],
    "distribution_fault": ["act.check_pressure", "act.report_leak"],
    "acidic_ph": ["act.flush_lines", "act.lab_test", "act.avoid_metal_vessels"],
    "alkaline_ph": ["act.flush_lines", "act.lab_test"],
    "cloudy": ["act.flush_lines", "act.clean_tank", "act.lab_test"],
    "slightly_cloudy": ["act.flush_lines", "act.clean_tank"],
    "very_high_tds": ["act.lab_test", "act.try_alternate_source"],
    "high_tds": ["act.lab_test", "act.try_alternate_source"],
    "low_do": ["act.flush_lines", "act.lab_test"],
    "very_low_do": ["act.flush_lines", "act.lab_test", "act.advisory"],
    "nothing_found": ["act.lab_test"],
}

# Capital / long-lead works, always listed AFTER the quick actions.
CAPITAL_WORKS = {
    "sewage": ["cap.sewage_repair", "cap.piping_replacement"],
    "acid_industrial": ["cap.effluent_enforcement", "cap.intake_protection"],
    "corrosive_soft": ["cap.ph_correction", "cap.piping_replacement"],
    "rusty_pipes": ["cap.piping_replacement", "cap.relining"],
    "hard_alkaline": ["cap.intake_treatment"],
    "algae_lime": ["cap.intake_treatment", "cap.source_protection"],
    "salinity": ["cap.alternate_source", "cap.intake_treatment"],
    "salty_taste": ["cap.alternate_source", "cap.effluent_enforcement"],
    "distribution_fault": ["cap.piping_replacement", "cap.repair_main"],
    "acidic_ph": ["cap.ph_correction", "cap.piping_replacement"],
    "alkaline_ph": ["cap.ph_correction"],
    "cloudy": ["cap.piping_replacement", "cap.intake_treatment"],
    "slightly_cloudy": ["cap.intake_treatment"],
    "very_high_tds": ["cap.alternate_source", "cap.intake_treatment"],
    "high_tds": ["cap.intake_treatment"],
    "low_do": ["cap.intake_treatment"],
    "very_low_do": ["cap.intake_treatment", "cap.sewage_repair"],
    "nothing_found": [],
}


# ---------------------------------------------------------------------------
# 6. Hotspots
# ---------------------------------------------------------------------------

def _as_datetime(value):
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).replace("T", " ")
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                     "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text[:26], fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def build_hotspots(readings, now=None):
    """Rank ward-level hotspots.

    Hotspot rule (AquaTrace brief):
      * 3 or more submissions with the SAME diagnosis in the SAME ward within
        the last 7 days, OR
      * any single CRITICAL submission.

    Ranking: severity (worst first), then number of people reporting, then how
    long the problem has lasted (longest first). Every hotspot is flagged
    ``needs_lab_confirmation``.

    ``readings`` are dicts with at least: ward, zone, severity, created_at and
    a list of diagnosis ``codes`` (or a full ``diagnosis`` dict).
    """
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(days=HOTSPOT_WINDOW_DAYS)
    groups = {}

    for r in readings:
        codes = r.get("codes")
        if codes is None:
            diag = r.get("diagnosis") or {}
            codes = [f["code"] for f in diag.get("findings", [])]
        severity = r.get("severity") or "NONE"
        created = _as_datetime(r.get("created_at"))
        if created is None:
            continue
        for code in codes:
            key = (r.get("ward"), r.get("zone"), code)
            groups.setdefault(key, []).append(
                {"created": created, "severity": severity, "row": r}
            )

    hotspots = []
    for (ward, zone, code), rows in groups.items():
        recent = [x for x in rows if x["created"] >= window_start]
        critical = any(x["severity"] == "CRITICAL" for x in recent)
        if len(recent) >= HOTSPOT_MIN_REPORTS or critical:
            worst = max(
                (x["severity"] for x in recent),
                key=lambda s: SEVERITY_ORDER.get(s, 0),
                default="NONE",
            )
            first_seen = min(x["created"] for x in recent)
            last_seen = max(x["created"] for x in recent)
            days_active = max(0, (now - first_seen).days)
            hotspots.append({
                "ward": ward,
                "zone": zone,
                "code": code,
                "severity": worst,
                "count": len({id(x["row"]) for x in recent}),
                "report_count": len(recent),
                "first_seen": first_seen,
                "last_seen": last_seen,
                "days_active": days_active,
                "needs_lab_confirmation": True,
                "quick_actions": QUICK_ACTIONS.get(code, ["act.lab_test"]),
                "capital_works": CAPITAL_WORKS.get(code, []),
                "first_action_key": "f.%s.action" % code,
                "department": _department_for(code),
                "status": _majority_status(recent),
            })

    hotspots.sort(key=lambda h: (
        -SEVERITY_ORDER.get(h["severity"], 0),
        -h["report_count"],
        -h["days_active"],
        str(h["ward"]),
    ))
    return hotspots


def _department_for(code):
    for f in diagnose_defaults(code):
        return f["department"]
    return "grievance"


def diagnose_defaults(code):
    """Return the canonical finding record for a finding code (dept + severity)."""
    probe = CODE_PROBES.get(code)
    if probe is None:
        return []
    result = diagnose(**probe)
    return [f for f in result["findings"] if f["code"] == code] or result["findings"]


def _majority_status(rows):
    counts = {}
    for x in rows:
        st = (x["row"].get("status") or "Submitted")
        counts[st] = counts.get(st, 0) + 1
    for st in STATUSES:
        if counts.get(st):
            return st
    return "Submitted"


# Small probes used to recover the canonical severity/department of a finding
# code without inventing a second place where the rules live.
CODE_PROBES = {
    "sewage": dict(ph=7.0, turbidity=8.0, tds=400.0, dissolved_oxygen=3.0,
                   reports=["bad_smell"]),
    "acid_industrial": dict(ph=5.5, turbidity=1.0, tds=800.0),
    "corrosive_soft": dict(ph=5.8, turbidity=1.0, tds=60.0),
    "rusty_pipes": dict(ph=6.0, turbidity=7.0, tds=300.0),
    "hard_alkaline": dict(ph=8.8, turbidity=1.0, tds=700.0),
    "algae_lime": dict(ph=8.8, turbidity=7.0, tds=300.0),
    "salinity": dict(ph=7.2, turbidity=0.5, tds=800.0),
    "salty_taste": dict(ph=7.2, turbidity=0.5, tds=800.0, reports=["salty_taste"]),
    "distribution_fault": dict(ph=7.2, turbidity=0.4, tds=250.0,
                               reports=["no_supply"]),
    "acidic_ph": dict(ph=6.1, turbidity=0.5, tds=300.0),
    "alkaline_ph": dict(ph=8.9, turbidity=0.5, tds=300.0),
    "cloudy": dict(ph=7.2, turbidity=7.0, tds=300.0),
    "slightly_cloudy": dict(ph=7.2, turbidity=2.0, tds=300.0),
    "very_high_tds": dict(ph=7.2, turbidity=0.5, tds=2500.0),
    "high_tds": dict(ph=7.2, turbidity=0.5, tds=1500.0),
    "low_do": dict(ph=7.2, turbidity=0.5, tds=300.0, dissolved_oxygen=3.0),
    "very_low_do": dict(ph=7.2, turbidity=0.5, tds=300.0, dissolved_oxygen=1.0),
    "nothing_found": dict(ph=7.2, turbidity=0.4, tds=250.0, dissolved_oxygen=6.0),
}


def finding_meta(code):
    """Severity + department + actions for a finding code (single lookup)."""
    defaults = diagnose_defaults(code)
    sev = defaults[0]["severity"] if defaults else "NONE"
    dept = defaults[0]["department"] if defaults else "grievance"
    if code == "salty_taste":
        sev, dept = "HIGH", "tpcb"
    if code == "nothing_found":
        sev, dept = "NONE", "grievance"
    return {
        "code": code,
        "severity": sev,
        "department": dept,
        "quick_actions": QUICK_ACTIONS.get(code, ["act.lab_test"]),
        "capital_works": CAPITAL_WORKS.get(code, []),
        "first_action_key": "f.%s.action" % code,
    }


# ---------------------------------------------------------------------------
# 7. Presentation helpers used by templates
# ---------------------------------------------------------------------------

STATUS_LABELS = {
    STATUS_OK: "status.ok",
    STATUS_WATCH: "status.watch",
    STATUS_UNSAFE: "status.unsafe",
}


def status_label_key(status):
    return STATUS_LABELS.get(status, "status.watch")
