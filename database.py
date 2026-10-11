"""
database.py -- SQLite storage for AquaTrace.
============================================

One file, one table for resident submissions (``readings``) plus a tiny
``hotspot_status`` table for the officials status workflow.

Privacy notes
-------------
* Only ward-level coordinates are stored. A resident's GPS point is resolved
  to the nearest ward marker before saving (see ``config.ward_centroid``), so
  exact user coordinates are never persisted or published.
* The only personal field is an optional first name.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

import config

DB_PATH = os.environ.get(
    "AQUATRACE_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "aquatrace.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ph               REAL NOT NULL,
    turbidity        REAL NOT NULL,
    tds              REAL NOT NULL,
    dissolved_oxygen REAL,
    reports          TEXT NOT NULL DEFAULT '[]',
    note             TEXT DEFAULT '',
    photo            TEXT DEFAULT '',
    first_name       TEXT DEFAULT '',
    ill              INTEGER NOT NULL DEFAULT 0,
    zone             TEXT NOT NULL,
    ward             TEXT NOT NULL,
    latitude         REAL,
    longitude        REAL,
    severity         TEXT NOT NULL DEFAULT 'NONE',
    status           TEXT NOT NULL DEFAULT 'Submitted',
    diagnosis        TEXT NOT NULL DEFAULT '{}',
    is_demo          INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hotspot_status (
    ward       TEXT NOT NULL,
    code       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'Submitted',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ward, code)
);

CREATE INDEX IF NOT EXISTS idx_readings_zone  ON readings(zone);
CREATE INDEX IF NOT EXISTS idx_readings_ward  ON readings(ward);
CREATE INDEX IF NOT EXISTS idx_readings_sev   ON readings(severity);
CREATE INDEX IF NOT EXISTS idx_readings_date  ON readings(created_at);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def insert_reading(payload):
    """Insert one resident submission. Returns the new reading id."""
    diagnosis = payload.get("diagnosis") or {}
    findings = diagnosis.get("findings") or []
    severity = "NONE"
    order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
    for f in findings:
        if order.get(f.get("severity"), 0) > order.get(severity, 0):
            severity = f.get("severity", "NONE")

    created_at = payload.get("created_at") or now_iso()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO readings
               (ph, turbidity, tds, dissolved_oxygen, reports, note, photo,
                first_name, ill, zone, ward, latitude, longitude, severity,
                status, diagnosis, is_demo, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                payload["ph"],
                payload["turbidity"],
                payload["tds"],
                payload.get("dissolved_oxygen"),
                json.dumps(payload.get("reports") or []),
                payload.get("note", "") or "",
                payload.get("photo", "") or "",
                payload.get("first_name", "") or "",
                1 if payload.get("ill") else 0,
                payload.get("zone") or config.DEFAULT_ZONE,
                payload.get("ward") or config.wards_for_zone(config.DEFAULT_ZONE)[0],
                payload.get("latitude"),
                payload.get("longitude"),
                severity,
                payload.get("status", "Submitted"),
                json.dumps(diagnosis),
                1 if payload.get("is_demo") else 0,
                created_at,
            ),
        )
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _row_to_dict(row, public=True):
    d = dict(row)
    try:
        d["reports"] = json.loads(d.get("reports") or "[]")
    except json.JSONDecodeError:
        d["reports"] = []
    try:
        d["diagnosis"] = json.loads(d.get("diagnosis") or "{}")
    except json.JSONDecodeError:
        d["diagnosis"] = {}
    d["ill"] = bool(d.get("ill"))
    d["is_demo"] = bool(d.get("is_demo"))
    d["status_hotspot"] = None
    if public:
        # Ward-level location only: never expose exact user coordinates.
        clat, clon = config.ward_centroid(d.get("zone"), d.get("ward"))
        d["latitude"], d["longitude"] = clat, clon
    return d


def get_reading(reading_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM readings WHERE id = ?",
                           (reading_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_readings(zone=None, ward=None, severity=None, problem=None,
                  date_from=None, date_to=None, statuses=None,
                  include_demo=True, limit=None, order="created_at DESC"):
    """Filtered list of readings. All filters are optional."""
    sql = ["SELECT * FROM readings WHERE 1=1"]
    args = []
    if zone:
        sql.append("AND zone = ?")
        args.append(zone)
    if ward:
        sql.append("AND ward = ?")
        args.append(ward)
    if severity:
        sql.append("AND severity = ?")
        args.append(severity)
    if date_from:
        sql.append("AND created_at >= ?")
        args.append(date_from)
    if date_to:
        # inclusive end date (accepts YYYY-MM-DD)
        if len(str(date_to)) == 10:
            date_to = date_to + " 23:59:59"
        sql.append("AND created_at <= ?")
        args.append(date_to)
    if statuses:
        marks = ",".join("?" for _ in statuses)
        sql.append("AND status IN (%s)" % marks)
        args.extend(list(statuses))
    if not include_demo:
        sql.append("AND is_demo = 0")
    if problem:
        sql.append("AND reports LIKE ?")
        args.append('%"%s"' % problem)
    sql.append("ORDER BY %s" % order)
    if limit:
        sql.append("LIMIT ?")
        args.append(int(limit))
    with connect() as conn:
        rows = conn.execute(" ".join(sql), args).fetchall()
    return [_row_to_dict(r) for r in rows]


def stats():
    """Live community stats for the Home page (Vellore-wide)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM readings").fetchone()["c"]
        today_count = conn.execute(
            "SELECT COUNT(*) c FROM readings WHERE created_at >= ?",
            (today,),
        ).fetchone()["c"]
        problem_wards = conn.execute(
            """SELECT COUNT(DISTINCT ward) c FROM readings
               WHERE severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"""
        ).fetchone()["c"]
        ward_count = conn.execute(
            "SELECT COUNT(DISTINCT ward) c FROM readings"
        ).fetchone()["c"]
        unsafe = conn.execute(
            """SELECT COUNT(*) c FROM readings
               WHERE severity IN ('HIGH','CRITICAL')"""
        ).fetchone()["c"]
        by_zone = conn.execute(
            """SELECT zone, COUNT(*) c,
                      SUM(CASE WHEN severity IN ('LOW','MEDIUM','HIGH','CRITICAL')
                               THEN 1 ELSE 0 END) problems
               FROM readings GROUP BY zone"""
        ).fetchall()
        by_status = conn.execute(
            "SELECT status, COUNT(*) c FROM readings GROUP BY status"
        ).fetchall()
    return {
        "total": total,
        "today": today_count,
        "problem_wards": problem_wards,
        "wards_covered": ward_count,
        "unsafe": unsafe,
        "by_zone": [dict(r) for r in by_zone],
        "by_status": {r["status"]: r["c"] for r in by_status},
        "zones": len(config.ZONES),
        "wards": len(config.ALL_WARDS),
    }


def set_status(reading_id, status):
    if status not in config_statuses():
        raise ValueError("bad status")
    with connect() as conn:
        conn.execute("UPDATE readings SET status = ? WHERE id = ?",
                     (status, reading_id))


def config_statuses():
    from water_diagnosis import STATUSES
    return STATUSES


def set_hotspot_status(ward, code, status):
    """Officials workflow: update a hotspot and the readings behind it."""
    if status not in config_statuses():
        raise ValueError("bad status")
    now = now_iso()
    with connect() as conn:
        conn.execute(
            """INSERT INTO hotspot_status (ward, code, status, updated_at)
               VALUES (?,?,?,?)
               ON CONFLICT(ward, code) DO UPDATE SET status = excluded.status,
                                                     updated_at = excluded.updated_at""",
            (ward, code, status, now),
        )
        rows = conn.execute(
            "SELECT id, diagnosis FROM readings WHERE ward = ?", (ward,)
        ).fetchall()
        for row in rows:
            try:
                diag = json.loads(row["diagnosis"] or "{}")
            except json.JSONDecodeError:
                continue
            codes = [f.get("code") for f in diag.get("findings", [])]
            if code in codes:
                conn.execute("UPDATE readings SET status = ? WHERE id = ?",
                             (status, row["id"]))


def get_hotspot_statuses():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM hotspot_status").fetchall()
    return {(r["ward"], r["code"]): {"status": r["status"],
                                     "updated_at": r["updated_at"]}
            for r in rows}


def hotspot_status_for(reading):
    """Status a resident sees for their own report."""
    diag = reading.get("diagnosis") or {}
    codes = [f.get("code") for f in diag.get("findings", [])]
    statuses = get_hotspot_statuses()
    best = None
    order = ["Submitted", "Verified", "In progress", "Resolved"]
    for code in codes:
        info = statuses.get((reading.get("ward"), code))
        if info:
            if best is None or order.index(info["status"]) > order.index(best["status"]):
                best = info
    return best["status"] if best else reading.get("status", "Submitted")


# ---------------------------------------------------------------------------
# Aggregate helpers used by the chart API
# ---------------------------------------------------------------------------

def average_by(rows, group_key, param):
    """Average of ``param`` grouped by ward or zone, only where present."""
    buckets = {}
    for r in rows:
        v = r.get(param)
        if v is None:
            continue
        label = r.get(group_key) or "-"
        buckets.setdefault(label, []).append(float(v))
    out = []
    for label, vals in buckets.items():
        out.append({
            "label": label,
            "avg": round(sum(vals) / len(vals), 2),
            "count": len(vals),
        })
    out.sort(key=_label_sort)
    return out


def _label_sort(item):
    """Wards sort by ward number, zones alphabetically."""
    label = str(item["label"])
    digits = "".join(ch for ch in label if ch.isdigit())
    return (1, int(digits), label) if digits else (0, 0, label)


def remove_demo_data():
    """Delete only rows created by 'Load demo data'."""
    with connect() as conn:
        conn.execute("DELETE FROM readings WHERE is_demo = 1")


def clear_all():
    """Wipe every submission (used by 'Remove demo data' only for demo rows)."""
    remove_demo_data()
    with connect() as conn:
        conn.execute("DELETE FROM hotspot_status")
