"""
demo_data.py -- clearly labelled sample data for AquaTrace.
===========================================================

The Home page, map, charts and officials dashboard all have "Load demo data"
and "Remove demo data" buttons. Demo rows are flagged ``is_demo = 1`` so they
can be removed without touching a real resident submission, and every demo
row is computed through ``water_diagnosis.diagnose()`` -- the same single
source of truth used for live submissions.

The data is spread across all four Vellore zones and many wards, with one
deliberate Katpadi cluster so the hotspot rule has something to show.
"""

from __future__ import annotations

import random

import config
import database
from water_diagnosis import diagnose

DEMO_NOTE = "Demo data"


def _scenario(rng, zone, ward, days_ago):
    """Return (ph, turbidity, tds, do, reports) for one plausible sample."""
    base = rng.choice([
        # (ph, turb, tds, do, reports) -- mostly healthy water
        (7.2, 0.6, 380, 5.4, []),
        (7.4, 0.8, 430, 5.0, []),
        (7.0, 1.4, 520, 4.8, ["cloudy_water"]),
        # Katpadi sewage cluster
        (6.9, 7.5, 640, 2.4, ["bad_smell", "cloudy_water"]),
        # Salinity / salty taste
        (7.3, 0.9, 1450, 5.1, ["salty_taste"]),
        # Corrosive soft water
        (6.1, 1.2, 70, 5.6, ["strange_colour"]),
        # Rusty pipes
        (6.2, 6.8, 340, 4.4, ["strange_colour", "cloudy_water"]),
        # Distribution faults
        (7.1, 0.5, 300, 5.2, ["no_supply"]),
        (7.3, 0.7, 410, 5.0, ["low_pressure"]),
        (7.2, 0.6, 390, 5.3, ["leak"]),
        # Hard, alkaline water
        (8.9, 1.1, 760, 4.9, []),
        # Very high TDS
        (7.1, 0.8, 2400, 5.0, ["salty_taste"]),
    ])
    ph, turb, tds, do, reports = base
    # Small day-to-day jitter so the charts are not flat.
    ph = round(min(14, max(0, ph + rng.uniform(-0.15, 0.15))), 1)
    turb = round(max(0, turb + rng.uniform(-0.4, 0.6)), 1)
    tds = round(max(0, tds + rng.uniform(-40, 60)), 0)
    do = round(max(0, do + rng.uniform(-0.4, 0.4)), 1)
    return ph, turb, tds, do, reports


def load_demo_data(count=160, seed=20261011):
    """Insert ``count`` demo submissions spread over the last 21 days."""
    database.remove_demo_data()  # never double-load
    rng = random.Random(seed)
    wards = config.ALL_WARDS
    created = []
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    for i in range(count):
        # Weight Katpadi (the first focus area) a little higher.
        if i % 10 < 4:
            zone = config.DEFAULT_ZONE
            ward = rng.choice(config.wards_for_zone(zone))
        else:
            ward = rng.choice(wards)
            zone = config.zone_for_ward(ward)

        days_ago = rng.randint(0, 20)
        # Build an explicit cluster: wards 46-48 get the sewage scenario often
        # so the hotspot rule (3+ same diagnosis in 7 days) triggers.
        if zone == config.DEFAULT_ZONE and ward in ("Ward 46", "Ward 47", "Ward 48") and i % 3 == 0:
            ph, turb, tds, do, reports = 6.9, 7.5, 640, 2.4, ["bad_smell", "cloudy_water"]
            days_ago = rng.randint(0, 6)
        else:
            ph, turb, tds, do, reports = _scenario(rng, zone, ward, days_ago)

        lat, lon = config.ward_centroid(zone, ward)
        created_at = (now - timedelta(days=days_ago,
                                      hours=rng.randint(0, 20),
                                      minutes=rng.randint(0, 59))
                      ).strftime("%Y-%m-%d %H:%M:%S")
        diagnosis = diagnose(ph=ph, turbidity=turb, tds=tds,
                             dissolved_oxygen=do, reports=reports)
        rid = database.insert_reading({
            "ph": ph,
            "turbidity": turb,
            "tds": tds,
            "dissolved_oxygen": do,
            "reports": reports,
            "note": DEMO_NOTE if i % 5 == 0 else "",
            "zone": zone,
            "ward": ward,
            "latitude": lat,
            "longitude": lon,
            "diagnosis": diagnosis,
            "is_demo": True,
            "created_at": created_at,
            "status": rng.choice(["Submitted", "Submitted", "Verified",
                                  "In progress", "Resolved"]),
        })
        created.append(rid)
    return len(created)
