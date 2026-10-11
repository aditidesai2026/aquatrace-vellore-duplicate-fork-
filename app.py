"""
app.py -- AquaTrace web application (Flask + SQLite).
=====================================================

AquaTrace: water quality monitoring and action planning for residents of
Vellore, Tamil Nadu (starting with Katpadi) and for Vellore City Municipal
Corporation (VCMC) officials.

Pages
    /                 Home: pitch, "Report a problem", live stats, contacts
    /check            Step-by-step reporting wizard (one question per screen)
    /result/<id>      Result: status, findings, "Report this to VCMC", banner
    /map              Community map (Leaflet), ward-level pins, filters
    /charts           Charts dashboard (Chart.js) + "My history"
    /learn            Short explainers for pH, turbidity, TDS, dissolved oxygen
    /contacts         Contact and Helpline
    /officials        Officials dashboard (simple password login)

REST endpoints
    GET  /api/stats   /api/areas  /api/contacts  /api/limits
    GET  /api/map     /api/charts /api/hotspots  /api/health
    POST /api/readings /api/validate /api/demo

All diagnosis logic lives in water_diagnosis.py (single source of truth).
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)

import config
import database
import demo_data
import water_diagnosis as wd

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024  # 3 MB uploads
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "static", "uploads")

# English strings come from the same file the browser uses for the language
# toggle, so there is exactly one place where every translation lives.
I18N_EN = {}


def _load_english():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "static", "js", "i18n.js")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return
    pattern = re.compile(r'^\s*"([^"]+)":\s*\[\s*"((?:[^"\\]|\\.)*)"\s*,', re.M)
    for m in pattern.finditer(text):
        I18N_EN[m.group(1)] = m.group(2).replace('\\"', '"')


_load_english()

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif"}


# ---------------------------------------------------------------------------
# Setup + template globals
# ---------------------------------------------------------------------------

database.init_db()


@app.context_processor
def inject_globals():
    return {
        "CONTACTS": config.CONTACTS,
        "LAST_CHECKED": config.LAST_CHECKED,
        "ZONES": config.ZONES,
        "WARDS_BY_ZONE": config.WARDS_BY_ZONE,
        "ALL_WARDS": config.ALL_WARDS,
        "DEFAULT_ZONE": config.DEFAULT_ZONE,
        "PRIMARY_CONTACT": config.PRIMARY_CONTACT,
        "APP_NAME": "AquaTrace",
        "now": datetime.now(timezone.utc),
        "is_official": bool(session.get("official")),
        "lang": request.args.get("lang") or session.get("lang") or "en",
        # Server-side English text for content the browser re-translates.
        "t": lambda key: I18N_EN.get(key, key),
    }


@app.template_filter("dt")
def format_dt(value, with_time=True):
    if not value:
        return ""
    text = str(value).replace("T", " ")
    try:
        parsed = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text
    return parsed.strftime("%d %b %Y, %I:%M %p").lstrip("0") if with_time \
        else parsed.strftime("%d %b %Y").lstrip("0")


@app.template_filter("dtshort")
def format_dt_short(value):
    if not value:
        return ""
    return str(value)[:10]


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_e):
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html", stats=database.stats())


@app.route("/check")
def check():
    return render_template("check.html")


@app.route("/result/<int:reading_id>")
def result(reading_id):
    reading = database.get_reading(reading_id)
    if not reading:
        abort(404)
    diagnosis = reading.get("diagnosis") or {}
    findings = diagnosis.get("findings") or []
    status = diagnosis.get("status", wd.STATUS_WATCH)
    return render_template(
        "result.html",
        reading=reading,
        diagnosis=diagnosis,
        findings=findings,
        status=status,
        status_key=wd.status_label_key(status),
        hotspot_status=database.hotspot_status_for(reading),
        report_message=build_report_message(reading, findings, status),
    )


@app.route("/map")
def map_page():
    return render_template("map.html")


@app.route("/charts")
def charts_page():
    return render_template("charts.html")


@app.route("/learn")
def learn_page():
    return render_template("learn.html")


@app.route("/contacts")
def contacts_page():
    return render_template("contacts.html")


# ---------------------------------------------------------------------------
# Reporting API
# ---------------------------------------------------------------------------

def _save_photo(file_storage):
    """Store an optional photo. Returns the public filename or ''."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        return ""
    name = file_storage.filename
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_IMAGE_EXT:
        return ""
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", name)[-40:]
    final = "%s_%s" % (datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"), safe)
    file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], final))
    return final


@app.route("/api/validate", methods=["POST"])
def api_validate():
    """Live validation used by the wizard (pH 0-14, no negatives, caps)."""
    clean, errors = wd.validate_reading(request.get_json(silent=True) or {})
    return jsonify({"ok": not errors, "errors": errors, "values": clean})


@app.route("/api/readings", methods=["POST"])
def api_create_reading():
    """Create a resident submission (no login required)."""
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        photo = ""
    else:
        payload = request.form.to_dict()
        photo = _save_photo(request.files.get("photo"))
        payload["ph"] = payload.get("ph")
        payload["dissolved_oxygen"] = payload.get("dissolved_oxygen") or None

    clean, errors = wd.validate_reading(payload)
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    # Reports (chips) -- accept a repeated form field, JSON list or comma string.
    if request.is_json or not request.form:
        reports = payload.get("reports") or []
    else:
        reports = request.form.getlist("reports") or payload.get("reports") or []
    if isinstance(reports, str):
        reports = [r for r in re.split(r"[,\s]+", reports) if r]
    reports = [r for r in reports if r in wd.REPORT_CHIPS]

    zone = payload.get("zone") or config.DEFAULT_ZONE
    if zone not in config.ZONES:
        zone = config.DEFAULT_ZONE
    wards = config.wards_for_zone(zone)
    ward = payload.get("ward")
    if ward not in wards:
        ward = wards[0]

    lat = payload.get("latitude")
    lon = payload.get("longitude")
    # Privacy: resolve the point to its ward marker; never store exact GPS.
    if lat not in (None, "") and lon not in (None, ""):
        if not config.in_vellore(lat, lon):
            return jsonify({
                "ok": False,
                "outside_vellore": True,
                "error": "Outside Vellore",
            }), 400
        near_zone, near_ward = config.nearest_ward(lat, lon)
        if near_zone:
            zone, ward = near_zone, near_ward
    lat, lon = config.ward_centroid(zone, ward)

    note = (payload.get("note") or "").strip()[:500]
    first_name = (payload.get("first_name") or "").strip()[:40]
    ill = str(payload.get("ill")).lower() in {"1", "true", "yes", "on"}

    diagnosis = wd.diagnose(
        ph=clean["ph"],
        turbidity=clean["turbidity"],
        tds=clean["tds"],
        dissolved_oxygen=clean["dissolved_oxygen"],
        reports=reports,
        ill=ill,
    )

    reading_id = database.insert_reading({
        "ph": clean["ph"],
        "turbidity": clean["turbidity"],
        "tds": clean["tds"],
        "dissolved_oxygen": clean["dissolved_oxygen"],
        "reports": reports,
        "note": note,
        "photo": photo,
        "first_name": first_name,
        "ill": ill,
        "zone": zone,
        "ward": ward,
        "latitude": lat,
        "longitude": lon,
        "diagnosis": diagnosis,
    })

    return jsonify({
        "ok": True,
        "id": reading_id,
        "status": diagnosis["status"],
        "redirect": url_for("result", reading_id=reading_id),
    })


# ---------------------------------------------------------------------------
# Data APIs (used by the map, charts and home stats)
# ---------------------------------------------------------------------------

@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "app": "AquaTrace"})


@app.route("/api/stats")
def api_stats():
    return jsonify(database.stats())


@app.route("/api/areas")
def api_areas():
    return jsonify({
        "zones": config.ZONES,
        "default_zone": config.DEFAULT_ZONE,
        "wards_by_zone": config.WARDS_BY_ZONE,
        "bounds": config.VELLORE_BOUNDS,
        "center": config.MAP_CENTER,
        "centroids": {
            z: {w: config.ward_centroid(z, w) for w in config.wards_for_zone(z)}
            for z in config.ZONES
        },
    })


@app.route("/api/contacts")
def api_contacts():
    return jsonify({"contacts": config.CONTACTS, "last_checked": config.LAST_CHECKED,
                    "order": config.DEPARTMENT_ORDER})


@app.route("/api/limits")
def api_limits():
    """Limits come straight from water_diagnosis.py (single source of truth)."""
    return jsonify({
        "ph": {"accept_min": wd.PH_ACCEPTABLE_MIN, "accept_max": wd.PH_ACCEPTABLE_MAX,
               "watch_min": wd.PH_WATCH_MIN, "watch_max": wd.PH_WATCH_MAX},
        "turbidity": {"acceptable": wd.TURBIDITY_ACCEPTABLE,
                      "problem": wd.TURBIDITY_PROBLEM},
        "tds": {"acceptable": wd.TDS_ACCEPTABLE, "taste": wd.TDS_TASTE,
                "permissible": wd.TDS_PERMISSIBLE},
        "dissolved_oxygen": {"warning": wd.DO_WARNING, "very_low": wd.DO_VERY_LOW},
        "severities": list(wd.SEVERITY_ORDER.keys()),
        "statuses": list(wd.STATUSES),
    })


def _filters_from_args():
    args = request.args
    return {
        "zone": args.get("zone") or None,
        "ward": args.get("ward") or None,
        "severity": args.get("severity") or None,
        "problem": args.get("problem") or None,
        "date_from": args.get("from") or None,
        "date_to": args.get("to") or None,
    }


@app.route("/api/map")
def api_map():
    """Ward-grouped, ward-level pins (never a resident's exact point)."""
    f = _filters_from_args()
    rows = database.list_readings(zone=f["zone"], ward=f["ward"],
                                  severity=f["severity"], problem=f["problem"],
                                  date_from=f["date_from"], date_to=f["date_to"],
                                  include_demo=True)
    order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
    grouped = {}
    for r in rows:
        key = (r["zone"], r["ward"])
        grouped.setdefault(key, []).append(r)

    wards = []
    for (zone, ward), items in grouped.items():
        worst = max(items, key=lambda x: order.get(x["severity"], 0))
        lat, lon = config.ward_centroid(zone, ward)
        codes = {}
        for it in items:
            for finding in (it.get("diagnosis") or {}).get("findings", []):
                meta = wd.finding_meta(finding["code"])
                codes[finding["code"]] = meta["severity"]
        wards.append({
            "zone": zone,
            "ward": ward,
            "lat": lat,
            "lon": lon,
            "count": len(items),
            "worst_severity": worst["severity"],
            "worst_status": worst["status"],
            "latest": max(i["created_at"] for i in items),
            "codes": codes,
            "reports": [{
                "id": it["id"],
                "created_at": it["created_at"],
                "severity": it["severity"],
                "status": database.hotspot_status_for(it),
                "ph": it["ph"],
                "turbidity": it["turbidity"],
                "tds": it["tds"],
                "dissolved_oxygen": it["dissolved_oxygen"],
                "reports": it["reports"],
                "is_demo": it["is_demo"],
                "findings": [f["code"] for f in
                             (it.get("diagnosis") or {}).get("findings", [])],
            } for it in sorted(items, key=lambda x: x["created_at"], reverse=True)],
        })
    wards.sort(key=lambda w: (-order.get(w["worst_severity"], 0), -w["count"],
                              w["zone"], w["ward"]))
    return jsonify({"wards": wards, "total": len(rows)})


@app.route("/api/hotspots")
def api_hotspots():
    rows = database.list_readings()
    hotspots = wd.build_hotspots(rows)
    statuses = database.get_hotspot_statuses()
    for h in hotspots:
        info = statuses.get((h["ward"], h["code"]))
        if info:
            h["status"] = info["status"]
        h["first_seen"] = h["first_seen"].strftime("%Y-%m-%d %H:%M:%S")
        h["last_seen"] = h["last_seen"].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"hotspots": hotspots})


def _histogram(values, edges):
    buckets = [{"from": edges[i], "to": edges[i + 1], "count": 0}
               for i in range(len(edges) - 1)]
    under, over = 0, 0
    for v in values:
        if v < edges[0]:
            under += 1
        elif v >= edges[-1]:
            over += 1
        else:
            for b in buckets:
                if b["from"] <= v < b["to"]:
                    b["count"] += 1
                    break
    return {"under": under, "over": over, "buckets": buckets}


@app.route("/api/charts")
def api_charts():
    """Everything the charts dashboard needs, filtered by zone and date range."""
    f = _filters_from_args()
    group = request.args.get("group") or "ward"
    if group not in ("ward", "zone"):
        group = "ward"
    rows = database.list_readings(zone=f["zone"], ward=f["ward"],
                                  severity=f["severity"], problem=f["problem"],
                                  date_from=f["date_from"], date_to=f["date_to"],
                                  include_demo=True)

    params = ["ph", "turbidity", "tds", "dissolved_oxygen"]
    avg = {p: database.average_by(rows, group, p) for p in params}

    # One line per zone over time (daily averages).
    zones_present = sorted({r["zone"] for r in rows}) or list(config.ZONES)
    series = {}
    for zone in zones_present:
        zrows = [r for r in rows if r["zone"] == zone]
        by_day = {}
        for r in zrows:
            day = r["created_at"][:10]
            bucket = by_day.setdefault(day, {p: [] for p in params} | {"count": 0})
            bucket["count"] += 1
            for p in params:
                if r[p] is not None:
                    bucket[p].append(float(r[p]))
        days = sorted(by_day)
        series[zone] = [{
            "date": d,
            "count": by_day[d]["count"],
            **{p: (round(sum(by_day[d][p]) / len(by_day[d][p]), 2)
                   if by_day[d][p] else None) for p in params},
        } for d in days]

    # Distributions (histograms).
    hist = {}
    edges = {
        "ph": [0, 5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 10, 14],
        "turbidity": [0, 1, 2, 3, 5, 8, 12, 20, 50, 100],
        "tds": [0, 100, 250, 500, 750, 1000, 1500, 2000, 3000, 5000, 50000],
        "dissolved_oxygen": [0, 1, 2, 3, 4, 5, 6, 8, 10, 14],
    }
    for p in params:
        vals = [float(r[p]) for r in rows if r[p] is not None]
        hist[p] = _histogram(vals, edges[p])

    # Severity + reported problem counts.
    severity_counts = {s: 0 for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]}
    for r in rows:
        severity_counts[r["severity"]] = severity_counts.get(r["severity"], 0) + 1
    problem_counts = {chip: 0 for chip in wd.REPORT_CHIPS}
    for r in rows:
        for chip in r["reports"]:
            if chip in problem_counts:
                problem_counts[chip] += 1

    # Readings per day and per zone (bar / heatmap).
    day_zone = {}
    for r in rows:
        day = r["created_at"][:10]
        day_zone.setdefault(day, {}).setdefault(r["zone"], 0)
        day_zone[day][r["zone"]] += 1

    # Ward-by-parameter heatmap: how many readings are out of range where.
    limits = {
        "ph": lambda v: not (wd.PH_ACCEPTABLE_MIN <= v <= wd.PH_ACCEPTABLE_MAX),
        "turbidity": lambda v: v > wd.TURBIDITY_PROBLEM,
        "tds": lambda v: v > wd.TDS_ACCEPTABLE,
        "dissolved_oxygen": lambda v: v < wd.DO_WARNING,
    }
    matrix = {}
    for r in rows:
        cell = matrix.setdefault(r["ward"], {
            "ward": r["ward"], "zone": r["zone"], "total": 0,
            "ph": 0, "turbidity": 0, "tds": 0, "dissolved_oxygen": 0,
        })
        cell["total"] += 1
        for p, test in limits.items():
            if r[p] is not None and test(float(r[p])):
                cell[p] += 1
    ward_matrix = sorted(matrix.values(), key=lambda c: -(
        c["ph"] + c["turbidity"] + c["tds"] + c["dissolved_oxygen"]))

    # Scatter points: pH vs TDS and pH vs turbidity, coloured by severity.
    scatter = [{
        "x": r["ph"], "y": r["tds"], "severity": r["severity"],
    } for r in rows if r["tds"] is not None]
    scatter_turb = [{
        "x": r["ph"], "y": r["turbidity"], "severity": r["severity"],
    } for r in rows if r["turbidity"] is not None]

    # Raw rows for "My history" and the scatter plots.
    slim = [{
        "id": r["id"], "created_at": r["created_at"], "zone": r["zone"],
        "ward": r["ward"], "severity": r["severity"], "status": r["status"],
        "ph": r["ph"], "turbidity": r["turbidity"], "tds": r["tds"],
        "dissolved_oxygen": r["dissolved_oxygen"], "reports": r["reports"],
        "is_demo": r["is_demo"],
    } for r in rows]

    return jsonify({
        "count": len(rows),
        "group": group,
        "avg": avg,
        "series": series,
        "hist": hist,
        "severity": severity_counts,
        "problems": problem_counts,
        "day_zone": day_zone,
        "ward_matrix": ward_matrix,
        "scatter": scatter,
        "scatter_turbidity": scatter_turb,
        "rows": slim,
    })


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

@app.route("/api/demo", methods=["POST"])
def api_demo():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    if action == "load":
        n = demo_data.load_demo_data()
        return jsonify({"ok": True, "action": "load", "count": n})
    if action == "remove":
        database.clear_all()
        return jsonify({"ok": True, "action": "remove"})
    return jsonify({"ok": False, "error": "unknown action"}), 400


# ---------------------------------------------------------------------------
# Officials dashboard (simple password login)
# ---------------------------------------------------------------------------

@app.route("/officials")
def officials():
    if not session.get("official"):
        return render_template("officials_login.html")
    return redirect(url_for("officials_dashboard"))


@app.route("/officials/login", methods=["POST"])
def officials_login():
    password = request.form.get("password", "")
    if password == config.OFFICIALS_PASSWORD:
        session["official"] = True
        return redirect(url_for("officials_dashboard"))
    flash("Wrong password. Please try again.", "error")
    return render_template("officials_login.html"), 401


@app.route("/officials/logout", methods=["POST"])
def officials_logout():
    session.pop("official", None)
    return redirect(url_for("home"))


def _officials_or_redirect():
    if not session.get("official"):
        abort(403)


@app.route("/officials/dashboard")
def officials_dashboard():
    _officials_or_redirect()
    rows = database.list_readings()
    hotspots = wd.build_hotspots(rows)
    statuses = database.get_hotspot_statuses()
    for h in hotspots:
        info = statuses.get((h["ward"], h["code"]))
        if info:
            h["status"] = info["status"]
            h["status_updated"] = info["updated_at"]
        else:
            h["status"] = h.get("status", "Submitted")
        h["first_seen_str"] = h["first_seen"].strftime("%d %b %Y")
        h["last_seen_str"] = h["last_seen"].strftime("%d %b %Y")
    recent = rows[:40]
    return render_template("officials.html", hotspots=hotspots, recent=recent,
                           stats=database.stats(), statuses=list(wd.STATUSES))


@app.route("/officials/status", methods=["POST"])
def officials_status():
    _officials_or_redirect()
    data = request.get_json(silent=True) or request.form.to_dict()
    status = data.get("status")
    if status not in wd.STATUSES:
        return jsonify({"ok": False, "error": "bad status"}), 400
    if data.get("ward") and data.get("code"):
        database.set_hotspot_status(data["ward"], data["code"], status)
    elif data.get("id"):
        try:
            database.set_status(int(data["id"]), status)
        except ValueError:
            return jsonify({"ok": False, "error": "bad id"}), 400
    else:
        return jsonify({"ok": False, "error": "missing target"}), 400
    return jsonify({"ok": True, "status": status})


@app.route("/officials/export.csv")
def officials_export_csv():
    """Weekly priority list as CSV."""
    _officials_or_redirect()
    rows = database.list_readings(
        date_from=(datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"))
    hotspots = wd.build_hotspots(rows)
    statuses = database.get_hotspot_statuses()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Rank", "Zone", "Ward", "Diagnosis", "Severity", "Reports",
        "First seen", "Days active", "Needs lab confirmation", "Status",
        "First action", "Responsible department", "Phone", "Email",
        "Quick low-cost actions", "Capital works",
    ])
    for i, h in enumerate(hotspots, start=1):
        info = statuses.get((h["ward"], h["code"]), {})
        contact = config.CONTACTS.get(h["department"], {})
        writer.writerow([
            i, h["zone"], h["ward"], h["code"], h["severity"], h["report_count"],
            h["first_seen"].strftime("%Y-%m-%d"), h["days_active"], "YES",
            info.get("status", h.get("status", "Submitted")),
            "f.%s.action" % h["code"],
            contact.get("dept", h["department"]),
            contact.get("phone", ""),
            contact.get("email", ""),
            "; ".join(h["quick_actions"]),
            "; ".join(h["capital_works"]),
        ])

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    output = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    from flask import send_file
    return send_file(output, mimetype="text/csv", as_attachment=True,
                     download_name="aquatrace-weekly-priority-%s.csv" % stamp)


@app.route("/officials/print")
def officials_print():
    """Printable weekly priority list (use the browser's Save as PDF)."""
    _officials_or_redirect()
    rows = database.list_readings(
        date_from=(datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"))
    hotspots = wd.build_hotspots(rows)
    statuses = database.get_hotspot_statuses()
    for h in hotspots:
        info = statuses.get((h["ward"], h["code"]))
        if info:
            h["status"] = info["status"]
        h["first_seen_str"] = h["first_seen"].strftime("%d %b %Y")
    return render_template("officials_print.html", hotspots=hotspots,
                           week_start=(datetime.now(timezone.utc) -
                                       timedelta(days=7)).strftime("%d %b %Y"))


@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ---------------------------------------------------------------------------
# Result page helper: pre-filled message for "Report this to VCMC"
# ---------------------------------------------------------------------------

def build_report_message(reading, findings, status):
    """Plain-text complaint a resident can copy or send by email."""
    labels = {
        "sewage": "likely sewage contamination",
        "acid_industrial": "acidic industrial/mine discharge or corrosion",
        "corrosive_soft": "soft, poorly buffered corrosive water",
        "rusty_pipes": "rusty corroded pipes or organic decay",
        "hard_alkaline": "hard carbonate-rich water or alkaline discharge",
        "algae_lime": "algae, lime or construction runoff",
        "salinity": "high salinity (neutral salts)",
        "salty_taste": "salinity or industrial discharge",
        "distribution_fault": "distribution fault (supply/pressure/leak)",
        "acidic_ph": "acidic pH",
        "alkaline_ph": "alkaline pH",
        "cloudy": "cloudy water (high turbidity)",
        "slightly_cloudy": "slightly cloudy water",
        "very_high_tds": "very high TDS",
        "high_tds": "high TDS",
        "low_do": "low dissolved oxygen",
        "very_low_do": "very low dissolved oxygen",
        "nothing_found": "no problem found in these readings",
    }
    problems = ", ".join(labels.get(f["code"], f["code"]) for f in findings) or "not sure"
    when = datetime.strptime(str(reading["created_at"])[:19],
                             "%Y-%m-%d %H:%M:%S").strftime("%d %B %Y at %I:%M %p")
    do = reading.get("dissolved_oxygen")
    lines = [
        "Water problem report - %s, %s (AquaTrace)" % (reading["ward"], reading["zone"]),
        "",
        "Time: %s" % when,
        "Readings: pH %s | Turbidity %s NTU | TDS %s mg/L | Dissolved oxygen %s"
        % (reading["ph"], reading["turbidity"], reading["tds"],
           ("%s mg/L" % do) if do is not None else "not tested"),
        "What we noticed: %s" % (", ".join(reading["reports"]).replace("_", " ") or "none"),
        "Diagnosis: %s" % problems,
        "Overall status: %s" % status,
        "",
        "This is an indicative community reading. Please send a laboratory-",
        "confirmed test if possible. Reported through AquaTrace, Vellore.",
    ]
    if reading.get("note"):
        lines.insert(5, "Note: %s" % reading["note"])
    return "\n".join(lines)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
