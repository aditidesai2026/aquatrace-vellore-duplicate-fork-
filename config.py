"""
config.py -- the ONE configuration file for AquaTrace.
======================================================

Everything a non-developer might need to update lives here:

  * CONTACTS      -- every helpline / department shown on the Home footer, the
                     Result page, the Contact and Helpline page and inside the
                     "Report this to VCMC" card. Phone numbers are tap-to-call,
                     emails are tap-to-email.
  * LAST_CHECKED -- the "last checked" date shown next to the contacts.
  * ZONES/WARDS  -- Vellore City Municipal Corporation's four zones and the
                    60 wards (Katpadi is the default zone).
  * VELLORE_BOUNDS / MAP_CENTER -- keeps the map and GPS checks inside Vellore.

Update a phone number here and it updates everywhere in the app.
"""

from __future__ import annotations

import math
import os

# Shown next to every contact list.
LAST_CHECKED = "11 October 2026"

# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------
# "to_confirm": True  ->  the value is a placeholder we still have to verify.
CONTACTS = {
    "commissioner": {
        "key": "commissioner",
        "dept": "Vellore City Municipal Corporation (VCMC)",
        "dept_ta": "வேலூர் நகராட்சி (VCMC)",
        "person": "The Commissioner, Vellore City Municipal Corporation",
        "address": "Infantry Road, Vellore 632001",
        "phone": "0416-2220578",
        "email": "commr.vellore@tn.gov.in",
        "website": "vcmc.in",
        "to_confirm": False,
        "blurb": "Head of the city corporation. Use for big or unresolved problems.",
    },
    "grievance": {
        "key": "grievance",
        "dept": "VCMC grievance / complaint line",
        "dept_ta": "VCMC குறைதீர்ப்பு எண்",
        "person": "VCMC Grievance Cell",
        "address": "Vellore City Municipal Corporation, Vellore 632001",
        "phone": "9280097911",
        "email": "iccc.vellore@gmail.com",
        "website": "",
        "to_confirm": False,
        "blurb": "Fastest way for residents to log a complaint.",
    },
    "engineer": {
        "key": "engineer",
        "dept": "City Engineer (water supply and pipelines)",
        "dept_ta": "நகர பொறியாளர் (குடிநீர் விநியோகம் மற்றும் குழாய்கள்)",
        "person": "City Engineer, VCMC",
        "address": "Vellore City Municipal Corporation, Vellore 632001",
        "phone": "7397389319",
        "email": "",
        "website": "",
        "to_confirm": False,
        "blurb": "Water supply, pipelines, pressure, leaks, tank cleaning.",
    },
    "works": {
        "key": "works",
        "dept": "Deputy Commissioner (Works)",
        "dept_ta": "துணை ஆணையர் (பணிகள்)",
        "person": "Deputy Commissioner (Works), VCMC",
        "address": "Vellore City Municipal Corporation, Vellore 632001",
        "phone": "9280097513",
        "email": "",
        "website": "",
        "to_confirm": False,
        "blurb": "Road work, drains and construction affecting water lines.",
    },
    "health": {
        "key": "health",
        "dept": "City Health Officer (sanitation and public health)",
        "dept_ta": "நகர சுகாதார அலுவலர் (துப்புரவு மற்றும் பொது சுகாதாரம்)",
        "person": "City Health Officer, VCMC",
        "address": "Vellore City Municipal Corporation, Vellore 632001",
        "phone": "9280097516",
        "email": "",
        "website": "",
        "to_confirm": False,
        "blurb": "Sewage smell, contamination, illness complaints, advisories.",
    },
    "zone_office": {
        "key": "zone_office",
        "dept": "Katpadi Zone office",
        "dept_ta": "காட்பாடி மண்டல அலுவலகம்",
        "person": "Zone Office, Katpadi Zone",
        "address": "Dharapadavedu, Katpadi, Vellore 632007  (address to confirm)",
        "phone": "",
        "email": "",
        "website": "",
        "to_confirm": True,
        "blurb": "Your local zone office. Address and phone to confirm.",
    },
    "twad": {
        "key": "twad",
        "dept": "Tamil Nadu water supply office, Katpadi",
        "dept_ta": "தமிழ்நாடு குடிநீர் வழங்கல் அலுவலகம், காட்பாடி",
        "person": "TN Water Supply Office",
        "address": "West Main Road, near S.M. Medical, Katpadi, Vellore 632006",
        "phone": "0416-2211224",
        "email": "",
        "website": "",
        "to_confirm": False,
        "blurb": "Regional water supply office for Katpadi.",
    },
    "tpcb": {
        "key": "tpcb",
        "dept": "Tamil Nadu Pollution Control Board, Vellore office",
        "dept_ta": "தமிழ்நாடு மாசுகட்டுப்பாடு வாரியம், வேலூர் அலுவலகம்",
        "person": "TN Pollution Control Board, Vellore",
        "address": "Vellore office  (address to confirm)",
        "phone": "",
        "email": "",
        "website": "",
        "to_confirm": True,
        "blurb": "Suspected industrial or factory discharge into water.",
    },
}

# Contact shown first in footers.
PRIMARY_CONTACT = "grievance"

# Which contact a finding's "responsible department" resolves to.
DEPARTMENT_ORDER = ["engineer", "health", "tpcb", "grievance", "commissioner",
                    "works", "twad", "zone_office"]

# ---------------------------------------------------------------------------
# Vellore only: four VCMC zones, 60 wards (15 per zone)
# ---------------------------------------------------------------------------
# Katpadi is the default zone for AquaTrace version 1.
# Ward numbering follows the 60-ward corporation split, 15 wards per zone.
# (Zone-wise ward numbers to be confirmed with VCMC before public launch.)

ZONES = ["Vellore Fort", "Sathuvachari", "Shenbakkam", "Katpadi"]

DEFAULT_ZONE = "Katpadi"

WARDS_BY_ZONE = {
    "Vellore Fort": [f"Ward {i}" for i in range(1, 16)],
    "Sathuvachari": [f"Ward {i}" for i in range(16, 31)],
    "Shenbakkam": [f"Ward {i}" for i in range(31, 46)],
    "Katpadi": [f"Ward {i}" for i in range(46, 61)],
}

ALL_WARDS = [w for z in ZONES for w in WARDS_BY_ZONE[z]]


def zone_for_ward(ward):
    for zone, wards in WARDS_BY_ZONE.items():
        if ward in wards:
            return zone
    return DEFAULT_ZONE


def wards_for_zone(zone):
    return WARDS_BY_ZONE.get(zone, WARDS_BY_ZONE[DEFAULT_ZONE])


# ---------------------------------------------------------------------------
# Geography -- keeps everything inside Vellore
# ---------------------------------------------------------------------------
# Approximate extent of Vellore city used to reject GPS fixes outside the city.
VELLORE_BOUNDS = {
    "min_lat": 12.85,
    "max_lat": 13.00,
    "min_lon": 79.05,
    "max_lon": 79.20,
}

# Map opens centred on Vellore (about 12.92 N, 79.13 E).
MAP_CENTER = [12.9236, 79.1320]
MAP_ZOOM = 12
MAP_MIN_ZOOM = 11
MAP_MAX_ZOOM = 17

# Rough zone centres (locality pins) used to place ward markers.
ZONE_CENTERS = {
    "Vellore Fort": (12.9180, 79.1320),
    "Sathuvachari": (12.9420, 79.1720),
    "Shenbakkam": (12.8990, 79.1130),
    "Katpadi": (12.9700, 79.1460),
}


def in_vellore(lat, lon):
    """True when a point falls inside the AquaTrace (Vellore) area."""
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return False
    return (VELLORE_BOUNDS["min_lat"] <= lat <= VELLORE_BOUNDS["max_lat"]
            and VELLORE_BOUNDS["min_lon"] <= lon <= VELLORE_BOUNDS["max_lon"])


def ward_centroid(zone, ward):
    """Approximate public marker for a ward.

    AquaTrace never publishes a resident's exact coordinates: every public pin
    is this ward-level point. Placement uses a deterministic golden-angle
    spiral around the zone centre so the same ward always maps to the same
    spot (no database of surveyed boundaries needed for version 1).
    """
    center = ZONE_CENTERS.get(zone) or ZONE_CENTERS[DEFAULT_ZONE]
    try:
        number = int("".join(ch for ch in str(ward) if ch.isdigit()) or 0)
    except ValueError:
        number = 0
    index = max(0, number - 1)
    golden = 2.399963229728653  # golden angle in radians
    ring = index // 5
    angle = index * golden
    radius = 0.004 + 0.0045 * ring
    lat = center[0] + radius * 0.75 * math.cos(angle)
    lon = center[1] + radius * math.sin(angle)
    return round(lat, 6), round(lon, 6)


def nearest_ward(lat, lon):
    """Ward whose public marker is closest to a GPS point (inside Vellore)."""
    if not in_vellore(lat, lon):
        return None, None
    best_zone, best_ward, best_d = None, None, None
    for zone, wards in WARDS_BY_ZONE.items():
        cz = ZONE_CENTERS[zone]
        for ward in wards:
            wlat, wlon = ward_centroid(zone, ward)
            d = (wlat - float(lat)) ** 2 + (wlon - float(lon)) ** 2
            if best_d is None or d < best_d:
                best_zone, best_ward, best_d = zone, ward, d
    return best_zone, best_ward


# ---------------------------------------------------------------------------
# Officials dashboard (simple password login)
# ---------------------------------------------------------------------------
# Override with the AQUATRACE_OFFICIALS_PASSWORD environment variable.
OFFICIALS_PASSWORD = os.environ.get("AQUATRACE_OFFICIALS_PASSWORD", "vellore-2026")
OFFICIALS_USER = "official"

# Optional Flask secret key override for production.
SECRET_KEY = os.environ.get("AQUATRACE_SECRET_KEY", "aquatrace-local-dev-key")
