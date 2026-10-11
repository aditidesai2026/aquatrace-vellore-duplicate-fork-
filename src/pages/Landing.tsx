import { useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  Droplet,
  FlaskConical,
  Map,
  BarChart3,
  BookOpen,
  Phone,
  ArrowRight,
  Mail,
} from "lucide-react";

/** The AquaTrace Flask app this landing page fronts. */
const APP = "http://127.0.0.1:5000";

type Lang = "en" | "ta";

const COPY: Record<Lang, Record<string, string>> = {
  en: {
    badge: "Serving Vellore, starting with Katpadi",
    navHow: "How it works",
    navExplore: "Explore",
    navContacts: "Contact",
    toggle: "தமிழ்",
    h1a: "Know what is in your water,",
    h1b: "and who to tell about it.",
    pitch:
      "AquaTrace helps residents of Vellore check their tap water in a few taps, see what is probably wrong, and report it to the right VCMC department. No sensors — you type what your test kit shows.",
    cta: "Report a problem",
    cta2: "How it works",
    note: "Opens the AquaTrace app (Flask). Start it with: python3 app.py",
    statZones: "VCMC zones",
    statWards: "wards covered",
    statSensors: "sensors — readings are typed in by people",
    howTitle: "How it works",
    how1t: "Type your readings",
    how1d:
      "pH, turbidity, TDS and optional dissolved oxygen. One question per screen, with a live colour gauge.",
    how2t: "See what is probably wrong",
    how2d:
      "Findings are checked against BIS IS 10500:2012 and WHO limits and sorted by severity.",
    how3t: "Report it to the right person",
    how3d:
      "Unsafe results come with a ready-made message and tap-to-call buttons for VCMC.",
    exploreTitle: "Explore AquaTrace",
    map: "Community map",
    mapD: "Ward-level pins coloured by severity, with filters.",
    charts: "Charts",
    chartsD: "Every reading, grouped by ward or zone.",
    learn: "Learn",
    learnD: "What pH, turbidity, TDS and DO mean.",
    contacts: "Contact and helpline",
    contactsD: "VCMC, zone office, TWAD and more.",
    safety: "This is indicative. It does NOT prove water is safe to drink. Bacteria, nitrate, fluoride, arsenic and heavy metals are not tested here — please confirm with a lab test.",
    contactsTitle: "Contact and helpline",
    lastChecked: "Last checked",
    engineer: "City Engineer (water supply and pipelines)",
    health: "City Health Officer (sanitation)",
    grievance: "VCMC grievance / complaint line",
    runTitle: "Run the app locally",
    runD: "pip install flask && python3 app.py — then open http://localhost:5000",
    offline:
      "AquaTrace server is not running yet. Start it with: python3 app.py",
    footer: "Community water reporting for Vellore",
  },
  ta: {
    badge: "வேலூருக்குச் சேவை — காட்பாடியிலிருந்து தொடங்குகிறோம்",
    navHow: "எப்படி செயல்படுகிறது",
    navExplore: "ஆராயுங்கள்",
    navContacts: "தொடர்பு",
    toggle: "English",
    h1a: "உங்கள் நீரில் என்ன உள்ளது என்று அறிய,",
    h1b: "யாரிடம் கூற வேண்டும் என்பதையும் அறிய.",
    pitch:
      "வேலூர் மக்கள் சில அழுத்தங்களில் தண்ணீரைச் சரிபார்த்து, என்ன பிரச்சினை என்று பார்த்து, சரியான VCMC துறைக்குப் புகாரளிக்க AquaTrace உதவுகிறது. சென்சார்கள் இல்லை — மக்களே அளவீடுகளை உள்ளிடுகிறார்கள்.",
    cta: "பிரச்சினையைப் புகாரளிக்கவும்",
    cta2: "எப்படி செயல்படுகிறது",
    note: "AquaTrace செயலியைத் திறக்கிறது (Flask). இயக்க: python3 app.py",
    statZones: "மண்டலங்கள்",
    statWards: "வார்டுகள்",
    statSensors: "சென்சார்கள் இல்லை — மக்களே அளவிடுகிறார்கள்",
    howTitle: "எப்படி செயல்படுகிறது",
    how1t: "உங்கள் அளவீடுகளை உள்ளிடவும்",
    how1d:
      "pH, குழமை, TDS மற்றும் விருப்பமான கரைந்த ஆக்ஸிஜன். ஒரு திரையில் ஒரு கேள்வி, நேரடி அளவுகோலுடன்.",
    how2t: "என்ன பிரச்சினை என்று பார்க்கவும்",
    how2d:
      "கண்டறிதல்கள் BIS IS 10500:2012 மற்றும் WHO வரம்புகளுடன் சரிபார்க்கப்பட்டு, தீவிரத்தின் அடிப்படையில் வரிசைப்படுத்தப்படுகின்றன.",
    how3t: "சரியான நபரிடம் புகாரளிக்கவும்",
    how3d:
      "பாதுகாப்பற்ற முடிவுகளுக்கு தயாரான செய்தியும் VCMC அழைப்பு பொத்தானும் உள்ளன.",
    exploreTitle: "AquaTrace ஐ ஆராயுங்கள்",
    map: "சமூக வரைபடம்",
    mapD: "தீவிரத்தின் அடிப்படையில் வார்டு அளவில் குறியீடுகள்.",
    charts: "விளக்கப்படங்கள்",
    chartsD: "ஒவ்வொரு அளவீடும் வார்டு அல்லது மண்டலம் வாரியாக.",
    learn: "அறிக",
    learnD: "pH, குழமை, TDS மற்றும் DO என்றால் என்ன.",
    contacts: "தொடர்பு மற்றும் உதவி எண்",
    contactsD: "VCMC, மண்டல அலுவலகம், TWAD மேலும் பல.",
    safety: "இது குறிப்பிட்ட நிலை மட்டுமே. குடிக்க நீர் பாதுகாப்பானது என்பதற்கு ஆதாரம் அல்ல. பாக்டீரியா, நைட்ரேட், ஃபுளோரைடு, ஆர்சனிக் மற்றும் கன உலோகங்கள் இங்கு சோதிக்கப்படவில்லை — ஆய்வகச் சோதனையால் உறுதிப்படுத்தவும்.",
    contactsTitle: "தொடர்பு மற்றும் உதவி எண்",
    lastChecked: "கடைசியாக சரிபார்த்தது",
    engineer: "நகர பொறியாளர் (குடிநீர் மற்றும் குழாய்கள்)",
    health: "நகர சுகாதார அலுவலர் (துப்புரவு)",
    grievance: "VCMC குறைதீர்ப்பு / புகார் எண்",
    runTitle: "செயலியை உள்ளூரில் இயக்கவும்",
    runD: "pip install flask && python3 app.py — பின்னர் http://localhost:5000",
    offline: "AquaTrace சர்வர் இன்னும் இயங்கவில்லை. இயக்கவும்: python3 app.py",
    footer: "வேலூருக்கான சமூக நீர் புகார் தளம்",
  },
};

/** Open the Flask app when it is running; explain how to start it when not. */
async function openApp(path: string) {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 2500);
    const res = await fetch(`${APP}/api/health`, { signal: ctrl.signal });
    clearTimeout(timer);
    if (res.ok) {
      const url = APP + path;
      const win = window.open(url, "_blank", "noopener");
      // Popup blocked? Follow the link in this tab instead.
      if (!win) window.location.href = url;
      return;
    }
  } catch {
    /* server not reachable */
  }
  toast("AquaTrace server is not running yet", {
    description: "Start it with: python3 app.py",
  });
}

const card =
  "rounded-3xl border border-white/80 bg-white/60 backdrop-blur-xl shadow-[0_10px_30px_-18px_rgba(11,59,111,0.45)]";

function Drop({ className = "" }: { className?: string }) {
  return <Droplet className={className} strokeWidth={2.2} />;
}

export default function Landing() {
  const [lang, setLang] = useState<Lang>("en");
  const c = COPY[lang];

  const stats = [
    { value: "4", label: c.statZones },
    { value: "60", label: c.statWards },
    { value: "0", label: c.statSensors },
  ];

  const explore = [
    { key: "map", icon: Map, path: "/map", title: c.map, desc: c.mapD },
    { key: "charts", icon: BarChart3, path: "/charts", title: c.charts, desc: c.chartsD },
    { key: "learn", icon: BookOpen, path: "/learn", title: c.learn, desc: c.learnD },
    { key: "contacts", icon: Phone, path: "/contacts", title: c.contacts, desc: c.contactsD },
  ];

  const helplines = [
    { label: c.grievance, phone: "9280097911", email: "iccc.vellore@gmail.com" },
    { label: c.engineer, phone: "7397389319", email: "" },
    { label: c.health, phone: "9280097516", email: "" },
  ];

  return (
    <div
      className="min-h-screen text-[#06283f]"
      style={{
        background:
          "linear-gradient(180deg,#f3fbff 0%,#e7f5ff 38%,#eefcf9 72%,#f7fdff 100%)",
      }}
    >
      {/* decorative water blobs — light glass only, no dark surfaces */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden>
        <span className="absolute -left-24 -top-24 h-[42vw] w-[42vw] rounded-full opacity-50 blur-[70px]" style={{ background: "radial-gradient(circle at 30% 30%, #7dd3fc, #bae6fd 60%, transparent 72%)" }} />
        <span className="absolute -right-32 top-1/4 h-[38vw] w-[38vw] rounded-full opacity-50 blur-[70px]" style={{ background: "radial-gradient(circle at 60% 40%, #99f6e4, #ccfbf1 60%, transparent 74%)" }} />
        <span className="absolute bottom-[-14vw] left-1/4 h-[44vw] w-[44vw] rounded-full opacity-50 blur-[70px]" style={{ background: "radial-gradient(circle at 50% 50%, #bfdbfe, #dbeafe 62%, transparent 76%)" }} />
      </div>

      {/* header */}
      <header className="sticky top-0 z-40 border-b border-white/70 bg-white/55 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <a href="/" className="flex items-center gap-2">
            <span
              className="grid h-9 w-9 place-items-center rounded-xl border border-white/70 text-white"
              style={{ background: "linear-gradient(140deg,#0ea5e9,#0d9488 55%,#0b3b6f)" }}
            >
              <Drop className="h-5 w-5" />
            </span>
            <span className="text-lg font-extrabold tracking-tight text-[#0b3b6f]">
              Aqua<span className="text-[#0d9488]">Trace</span>
            </span>
          </a>

          <nav className="hidden items-center gap-1 md:flex">
            <a href="#how" className="rounded-lg px-3 py-2 text-sm font-semibold text-[#0b3b6f] hover:bg-white/80">
              {c.navHow}
            </a>
            <a href="#explore" className="rounded-lg px-3 py-2 text-sm font-semibold text-[#0b3b6f] hover:bg-white/80">
              {c.navExplore}
            </a>
            <a href="#contacts" className="rounded-lg px-3 py-2 text-sm font-semibold text-[#0b3b6f] hover:bg-white/80">
              {c.navContacts}
            </a>
          </nav>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setLang(lang === "en" ? "ta" : "en")}
              className="rounded-full border border-white/90 bg-white/75 px-3 py-1.5 text-xs font-bold text-[#0b3b6f] transition hover:bg-white"
              aria-label="Switch language"
            >
              {c.toggle}
            </button>
            <button
              type="button"
              onClick={() => openApp("/check")}
              className="hidden rounded-xl border border-white/50 px-4 py-2.5 text-sm font-bold text-white transition hover:-translate-y-0.5 sm:inline-flex"
              style={{
                background: "linear-gradient(135deg,#0284c7,#0d9488 70%)",
                boxShadow: "0 14px 30px -16px rgba(2,132,199,.95)",
              }}
            >
              {c.cta}
            </button>
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-14">
        {/* hero */}
        <motion.section
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className={`${card} p-6 sm:p-10`}
        >
          <span className="inline-flex items-center gap-2 rounded-full border border-white/90 bg-teal-100/80 px-3 py-1 text-xs font-bold text-teal-800">
            <Drop className="h-3.5 w-3.5" /> {c.badge}
          </span>

          <h1 className="mt-5 text-3xl font-extrabold leading-[1.05] tracking-tight text-[#0b3b6f] sm:text-5xl">
            {c.h1a}
            <br />
            <span
              className="bg-clip-text text-transparent"
              style={{ backgroundImage: "linear-gradient(90deg,#38bdf8,#0e7490,#0d9488)" }}
            >
              {c.h1b}
            </span>
          </h1>

          <p className="mt-4 max-w-2xl text-base text-[#06283f]/75 sm:text-lg">{c.pitch}</p>

          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => openApp("/check")}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl border border-white/60 px-6 py-4 text-lg font-bold text-white transition hover:-translate-y-0.5"
              style={{
                background: "linear-gradient(135deg,#0284c7,#0d9488 70%)",
                boxShadow: "0 18px 34px -18px rgba(2,132,199,.95)",
              }}
            >
              {c.cta} <ArrowRight className="h-5 w-5" />
            </button>
            <a
              href="#how"
              className="inline-flex flex-1 items-center justify-center rounded-2xl border border-white/95 bg-white/80 px-6 py-4 text-lg font-bold text-[#0b3b6f] transition hover:bg-white"
            >
              {c.cta2}
            </a>
          </div>
          <p className="mt-3 text-xs text-[#06283f]/55">{c.note}</p>

          <div className="mt-7 grid gap-3 sm:grid-cols-3">
            {stats.map((s) => (
              <div key={s.label} className="rounded-2xl border border-white/90 bg-white/55 p-4">
                <p className="text-3xl font-extrabold tracking-tight text-[#0b3b6f]">{s.value}</p>
                <p className="mt-1 text-xs font-bold uppercase tracking-widest text-[#0e7490]">
                  {s.label}
                </p>
              </div>
            ))}
          </div>
        </motion.section>

        {/* how it works */}
        <motion.section
          id="how"
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.5 }}
          className="mt-8"
        >
          <h2 className="text-xl font-extrabold tracking-tight text-[#0b3b6f] sm:text-2xl">
            {c.howTitle}
          </h2>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {[
              { n: 1, t: c.how1t, d: c.how1d },
              { n: 2, t: c.how2t, d: c.how2d },
              { n: 3, t: c.how3t, d: c.how3d },
            ].map((step) => (
              <div key={step.n} className={`${card} p-5`}>
                <span
                  className="grid h-9 w-9 place-items-center rounded-xl border border-white/80 text-sm font-extrabold text-white"
                  style={{ background: "linear-gradient(135deg,#0ea5e9,#0d9488)" }}
                >
                  {step.n}
                </span>
                <h3 className="mt-3 font-extrabold tracking-tight text-[#0b3b6f]">{step.t}</h3>
                <p className="mt-1 text-sm text-[#06283f]/70">{step.d}</p>
              </div>
            ))}
          </div>
        </motion.section>

        {/* safety banner */}
        <motion.section
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5 }}
          className={`${card} mt-8 flex gap-3 p-5 ring-1 ring-sky-300/70`}
        >
          <FlaskConical className="mt-0.5 h-5 w-5 shrink-0 text-[#0e7490]" />
          <p className="text-sm font-semibold text-[#0b3b6f]">{c.safety}</p>
        </motion.section>

        {/* explore */}
        <motion.section
          id="explore"
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.5 }}
          className="mt-8"
        >
          <h2 className="text-xl font-extrabold tracking-tight text-[#0b3b6f] sm:text-2xl">
            {c.exploreTitle}
          </h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {explore.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => openApp(item.path)}
                  className={`${card} p-5 text-left transition hover:-translate-y-1 hover:bg-white/80`}
                >
                  <Icon className="h-5 w-5 text-[#0d9488]" />
                  <p className="mt-3 font-extrabold tracking-tight text-[#0b3b6f]">
                    {item.title}
                  </p>
                  <p className="mt-1 text-sm text-[#06283f]/70">{item.desc}</p>
                </button>
              );
            })}
          </div>
        </motion.section>

        {/* contacts */}
        <motion.section
          id="contacts"
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.5 }}
          className="mt-8"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-extrabold tracking-tight text-[#0b3b6f] sm:text-2xl">
              {c.contactsTitle}
            </h2>
            <span className="rounded-full border border-white/90 bg-white/60 px-3 py-1 text-xs font-bold text-[#0b3b6f]">
              {c.lastChecked}: 11 October 2026
            </span>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            {helplines.map((h) => (
              <div key={h.phone} className={`${card} p-5`}>
                <p className="font-bold text-[#0b3b6f]">{h.label}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <a
                    href={`tel:${h.phone}`}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-white/95 bg-white/80 px-3 py-2 text-sm font-bold text-[#0b3b6f] transition hover:bg-white"
                  >
                    <Phone className="h-4 w-4" /> {h.phone}
                  </a>
                  {h.email && (
                    <a
                      href={`mailto:${h.email}`}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-white/95 bg-white/80 px-3 py-2 text-sm font-bold text-[#0b3b6f] transition hover:bg-white"
                    >
                      <Mail className="h-4 w-4" /> Email
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className={`${card} mt-4 p-5`}>
            <p className="font-bold text-[#0b3b6f]">{c.runTitle}</p>
            <code className="mt-2 block rounded-xl border border-white/90 bg-white/70 px-3 py-2 text-sm text-[#0e7490]">
              {c.runD}
            </code>
          </div>
        </motion.section>
      </main>

      <footer className="relative z-10 mt-6 border-t border-white/70 bg-white/50 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-sm text-[#06283f]/70 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>
            © {new Date().getFullYear()} AquaTrace · {c.footer}
          </p>
          <button
            type="button"
            onClick={() => openApp("/")}
            className="font-bold text-[#0e7490] underline decoration-[#0d9488]/60 underline-offset-4"
          >
            {c.cta} →
          </button>
        </div>
      </footer>
    </div>
  );
}
