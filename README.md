# AquaTrace

**Water quality monitoring and action planning for Vellore, Tamil Nadu — starting with Katpadi.**

Residents type in what their test kit tells them (pH, turbidity, TDS, optional dissolved
oxygen) plus what they can see, smell or taste. AquaTrace checks those numbers against
BIS IS 10500:2012 and WHO limits, says what is probably wrong, who is responsible, and
writes the complaint message for the Vellore City Municipal Corporation (VCMC).

There are **no sensors and no hardware** — every reading is typed in by a person.
There is **no login for residents**: anyone can report a water problem.

---

## Run it

```bash
pip install flask          # only dependency
python3 app.py             # http://localhost:5000
```

Optional environment variables:

| Variable | Default | What it does |
| --- | --- | --- |
| `PORT` | `5000` | HTTP port |
| `AQUATRACE_DB` | `./aquatrace.db` | SQLite file |
| `AQUATRACE_OFFICIALS_PASSWORD` | `vellore-2026` | Officials dashboard password |
| `AQUATRACE_SECRET_KEY` | dev value | Flask session secret (set this in production) |

Load sample data with the clearly labelled **Load demo data** button on the Home page or
the officials dashboard (spread across all four zones and 60 wards). **Remove demo data**
deletes only demo rows, never a real report.

---

## Pages

| Route | What it is |
| --- | --- |
| `/` | Home: one-line pitch, big **Report a problem** button, live community stats, contact footer |
| `/check` | Six-screen wizard, one question per screen, progress bar, number box + slider + live colour gauge |
| `/result/<id>` | Status card (Looks OK / Watch / Unsafe), findings by severity, **Report this to VCMC**, disclaimer |
| `/map` | Leaflet map of Vellore, ward-level pins coloured by severity, filters |
| `/charts` | Chart.js dashboard: averages with limit lines, trends, histograms, scatter, heatmaps, **My history** |
| `/learn` | Explainers for pH, turbidity, TDS and dissolved oxygen, test-kit guide, limits table |
| `/contacts` | Every helpline, tap-to-call and tap-to-email, with a "last checked" date |
| `/officials` | Officials dashboard behind a simple password: ranked hotspots, status workflow, CSV + printable PDF |

Language toggle (**English / தமிழ்**) sits in the header on every page and is remembered
in the browser. Every technical term carries a tooltip (hover or keyboard-focus the `?`).

---

## Where the logic lives

```
water_diagnosis.py   ← SINGLE SOURCE OF TRUTH. Limits, validation, gauges,
                        every finding rule, severity ordering, hotspot rule.
config.py            ← The one config file: contacts, "last checked", 4 zones,
                        60 wards, Vellore bounds, officials password.
database.py          ← SQLite schema + queries (readings, hotspot status).
demo_data.py         ← Sample data, computed through the same diagnose() function.
app.py               ← Flask routes + REST endpoints.
templates/           ← Jinja pages.   static/  ← CSS, JS, uploads.
tests/               ← Unit tests for the rules + route/API smoke tests.
```

### Limits (cited in `water_diagnosis.py`)

| Parameter | Acceptable | Watch | Problem | Source |
| --- | --- | --- | --- | --- |
| pH | 6.5 – 8.5 | 6.0–6.5, 8.5–9.0 | < 6.0 or > 9.0 | BIS IS 10500:2012 · WHO |
| Turbidity | ≤ 1 NTU | 1 – 5 NTU | > 5 NTU | BIS IS 10500:2012 |
| TDS | ≤ 500 mg/L | 500 – 2000 mg/L | > 2000 mg/L | BIS acceptable 500 / permissible 2000; WHO taste > 1000 |
| Dissolved oxygen | ≥ 4 mg/L | 2 – 4 mg/L | < 2 mg/L | **AquaTrace project rule — not a drinking water standard** |

### Combined rules implemented

- Turbidity > 5 **+** DO < 4 **+** smell reported → **likely sewage contamination (CRITICAL)**
- Low pH + TDS > 500 → acidic industrial/mine discharge or corrosion releasing metals **(HIGH)**
- Low pH + TDS < 100 → soft, poorly buffered, corrosive water **(MEDIUM)**
- Low pH + turbidity > 5 → rusty corroded pipes or organic decay **(HIGH)**
- High pH + TDS > 500 + normal turbidity → hard carbonate-rich water or alkaline discharge **(MEDIUM)**
- High pH + turbidity > 5 → algae / lime / construction runoff; chlorine works less well here **(MEDIUM)**
- Normal pH + TDS > 500 → neutral salts (salinity) — pH alone would miss this **(LOW)**
- Salty taste + TDS > 500 → salinity or industrial discharge **(HIGH)**
- All readings normal + no supply / low pressure / leak → distribution fault **(MEDIUM)**
- Nothing found → says so, and **never** says the water is safe

Each finding carries a severity, a first action and a responsible department:
water supply and pipelines → **City Engineer**, sanitation → **City Health Officer**,
suspected industrial discharge → **TN Pollution Control Board**.

### Hotspot rule

Grouped by ward: **3+ submissions with the same diagnosis in the same ward within 7 days**,
or **any single CRITICAL** submission. Ranked by severity → number of people reporting →
how long the problem has lasted. Quick low-cost actions (flushing, tank cleaning,
chlorination, advisories) are listed before capital works, and **every hotspot is flagged
"needs lab confirmation"**.

---

## Tests

```bash
python3 tests/test_water_diagnosis.py     # 39 unit tests for the rules
python3 tests/test_app.py                 # 19 route / API / privacy smoke tests
```

Both suites use only the standard library `unittest`.

---

## Privacy

- **Ward-level locations only.** A GPS point is checked against the Vellore bounds, mapped
  to the nearest ward marker, and only that marker is stored and published. Exact user
  coordinates are never persisted or returned by any API.
- The only personal field is an **optional first name**. No login, phone number or email.
- Outside Vellore? The app shows *"AquaTrace currently serves Vellore only"* and asks you
  to pick a ward manually.
- Every result carries the banner: *This is indicative. It does NOT prove water is safe to
  drink. Bacteria, nitrate, fluoride, arsenic and heavy metals are not tested here.*

---

## REST endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/readings` | Create a submission (form or JSON) |
| `POST` | `/api/validate` | Live validation used by the wizard |
| `GET` | `/api/limits` | Limits straight out of `water_diagnosis.py` |
| `GET` | `/api/stats` | Home page community stats |
| `GET` | `/api/areas` | Zones, 60 wards, ward markers, Vellore bounds |
| `GET` | `/api/map` | Ward-grouped pins (`zone`, `severity`, `problem`, `from`, `to`) |
| `GET` | `/api/charts` | Aggregates for every chart (`group=ward\|zone`) |
| `GET` | `/api/hotspots` | Ranked hotspots with status |
| `GET` | `/api/contacts` | Contacts + last-checked date |
| `POST` | `/api/demo` | `{action: "load"}` / `{action: "remove"}` |
| `POST` | `/officials/status` | Status workflow (Submitted → Verified → In progress → Resolved) |
| `GET` | `/officials/export.csv` | Weekly priority list as CSV |
| `GET` | `/officials/print` | Printable weekly priority list (browser → Save as PDF) |

---

## Configuration

All contacts live in **one file**, `config.py`, and appear on the Home footer, the Result
page, the Contact page and the "Report this to VCMC" card. Entries marked
`to_confirm: True` (Katpadi zone office, TN Pollution Control Board Vellore) show a
"to confirm" badge until the details are verified. Update `LAST_CHECKED` in the same file
and the date updates everywhere.

---

## Note on the React shell in this repository

The Freebuff preview in this repo runs Vite + React, so the project's `/` landing page
(`src/pages/Landing.tsx`) is an AquaTrace-branded front door for the preview. The
application itself — everything you interact with — is the Flask app described above.
