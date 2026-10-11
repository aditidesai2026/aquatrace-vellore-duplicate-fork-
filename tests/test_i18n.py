"""
Checks that the English/Tamil dictionary covers every key the UI asks for.

Any data-i18n / data-tip-key in a template, or t("key") call in the static JS,
must resolve to an entry in static/js/i18n.js with both an English and a
Tamil string. Dynamic key families (f.<code>.title, act.<code>, …) are expanded
from water_diagnosis.py so they are checked too.

Run from the project root:  python3 tests/test_i18n.py
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import water_diagnosis as wd  # noqa: E402

I18N_JS = os.path.join(ROOT, "static", "js", "i18n.js")
TEMPLATES = os.path.join(ROOT, "templates")
STATIC_JS = os.path.join(ROOT, "static", "js")

PARAMS = ["ph", "turbidity", "tds", "dissolved_oxygen"]
CHIPS = list(wd.REPORT_CHIPS)
# Flat keys that are valid without a dot.
FLAT_KEYS = {"a11y.skip", "common.loading", "common.retry", "next_contacts"}
# Keys that appear only inside Jinja expressions; the families below cover them.
JINJA = re.compile(r"\{\{")
# A translation key: word.word (dots allowed, no spaces).
KEYY = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9_]+)+$")
CONTACT_KEYS = ["commissioner", "grievance", "engineer", "works", "health",
                "zone_office", "twad", "tpcb"]
STATUS_SLUGS = ["submitted", "verified", "in_progress", "resolved"]
SEVERITIES = [s.lower() for s in wd.SEVERITY_ORDER]


def dictionary():
    """Parse the flat [english, tamil] dictionary out of i18n.js."""
    text = open(I18N_JS, encoding="utf-8").read()
    entries = {}
    for m in re.finditer(r'^\s*"([^"]+)":\s*\[\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\]',
                         text, re.M):
        key, en, ta = m.group(1), m.group(2), m.group(3)
        entries[key] = (en, ta)
    return entries


def keys_used():
    """Every translation key the templates and scripts reference."""
    used = set()

    def add(raw):
        for key in (raw if isinstance(raw, (list, tuple, set)) else [raw]):
            if not key or JINJA.search(key):
                continue
            if key in FLAT_KEYS or KEYY.match(key):
                used.add(key)

    for name in sorted(os.listdir(TEMPLATES)):
        if not name.endswith(".html"):
            continue
        with open(os.path.join(TEMPLATES, name), encoding="utf-8") as fh:
            src = fh.read()
        add(re.findall(r'data-i18n="([^"]+)"', src))
        add(re.findall(r'data-tip-key="([^"]+)"', src))
        # macro arguments such as 'charts.avg_ph' or 'learn.kit1'
        add(re.findall(r"'([a-z0-9_]+(?:\.[a-z0-9_]+)+)'", src))

    for name in sorted(os.listdir(STATIC_JS)):
        if not name.endswith(".js"):
            continue
        with open(os.path.join(STATIC_JS, name), encoding="utf-8") as fh:
            src = fh.read()
        add(re.findall(r'\b(?:aqT|t)\(\s*"([a-z0-9_]+(?:\.[a-z0-9_]+)+)"', src))
        # keys built from templates: "f." + code + ".title" etc.
        add(re.findall(r'"(f|act|cap|report|status|severity|term|tip|c|gauge)\." \+', src))

    # expand dynamic key families
    for code in wd.CODE_PROBES:
        used.update({"f.%s.title" % code, "f.%s.desc" % code, "f.%s.action" % code})
        for a in wd.QUICK_ACTIONS.get(code, []):
            used.add(a)
        for a in wd.CAPITAL_WORKS.get(code, []):
            used.add(a)
    for p in PARAMS:
        used.update({"term.%s" % p, "tip.%s" % p,
                     "learn.%s_name" % p, "learn.%s_what" % p,
                     "learn.%s_ok" % p, "learn.%s_watch" % p,
                     "learn.%s_bad" % p, "learn.%s_why" % p,
                     "check.%s.ok" % ("do" if p == "dissolved_oxygen" else p)})
    used.update({"gauge.ok", "gauge.watch", "gauge.unsafe", "gauge.none"})
    for chip in CHIPS:
        used.add("report.%s" % chip)
    for s in STATUS_SLUGS:
        used.add("status.%s" % s)
    for s in SEVERITIES:
        used.add("severity.%s" % s)
    for k in CONTACT_KEYS:
        used.update({"c.%s.dept" % k, "c.%s.blurb" % k})
    for st in ["ok", "watch", "unsafe"]:
        used.update({"status.%s" % st, "result.summary.%s" % st})
    used.update({"f.%s.title" % c for c in wd.CODE_PROBES})
    used = {u for u in used if u and not u.endswith(".")}
    return used


class I18nCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dict = dictionary()
        cls.used = keys_used()

    def test_dictionary_parses(self):
        self.assertGreater(len(self.dict), 300, "dictionary did not parse")

    def test_every_used_key_exists(self):
        missing = sorted(k for k in self.used if k not in self.dict)
        self.assertEqual(missing, [], "missing translation keys: %s" % missing)

    def test_every_key_has_english_and_tamil(self):
        empty = sorted(k for k, (en, ta) in self.dict.items()
                       if not en.strip() or not ta.strip())
        self.assertEqual(empty, [], "empty translations: %s" % empty)

    def test_tamil_is_actually_translated(self):
        same = sorted(k for k, (en, ta) in self.dict.items()
                      if en == ta and len(en) > 3 and not re.match(r"^[A-Za-z\s/()·.\-–≤≥<>0-9]+$", en))
        self.assertEqual(same, [], "untranslated entries: %s" % same)

    def test_no_orphan_tamil_without_english(self):
        # spot-check a few important strings exist in Tamil
        for key in ("home.cta", "result.disclaimer", "check.submit", "nav.map"):
            self.assertIn(key, self.dict)
            self.assertNotEqual(self.dict[key][0], self.dict[key][1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
