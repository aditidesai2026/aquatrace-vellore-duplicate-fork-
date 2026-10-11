/* AquaTrace — shared UI behaviour */
(function () {
  "use strict";

  /* ---------- toast ---------- */
  window.aqToast = function (message) {
    var el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(el._timer);
    el._timer = setTimeout(function () { el.classList.remove("show"); }, 3200);
  };

  function t(key, vars) {
    return window.aqT ? window.aqT(key, vars) : key;
  }

  /* ---------- language toggle ---------- */
  var langBtn = document.getElementById("lang-toggle");
  if (langBtn) {
    langBtn.addEventListener("click", function () {
      var next = (window.AquaI18n.lang === "ta") ? "en" : "ta";
      window.AquaI18n.setLang(next);
    });
  }

  /* ---------- mobile menu ---------- */
  var menuBtn = document.getElementById("menu-btn");
  var mobileNav = document.getElementById("mobile-nav");
  if (menuBtn && mobileNav) {
    menuBtn.addEventListener("click", function () {
      var open = !mobileNav.classList.contains("hidden");
      mobileNav.classList.toggle("hidden", open);
      menuBtn.setAttribute("aria-expanded", String(!open));
    });
  }

  /* ---------- live community stats (home) ---------- */
  var statToday = document.getElementById("stat-today");
  if (statToday) {
    var loading = document.getElementById("stats-loading");
    var emptyBox = document.getElementById("stats-empty");
    var zonesLine = document.getElementById("stats-zones");
    fetch("/api/stats")
      .then(function (r) { return r.json(); })
      .then(function (s) {
        if (loading) loading.classList.add("hidden");
        statToday.textContent = s.today;
        document.getElementById("stat-problem-wards").textContent = s.problem_wards;
        document.getElementById("stat-total").textContent = s.total;
        if (zonesLine) {
          zonesLine.textContent = t("home.stats_zones", { zones: s.zones, wards: s.wards });
        }
        if (!s.total && emptyBox) emptyBox.classList.remove("hidden");
      })
      .catch(function () {
        if (loading) loading.textContent = t("error.generic");
      });
  }

  /* ---------- demo data buttons ---------- */
  function wireDemo(id, action) {
    var btn = document.getElementById(id);
    if (!btn) return;
    btn.addEventListener("click", function () {
      btn.disabled = true;
      fetch("/api/demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: action })
      })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          btn.disabled = false;
          if (!res.ok) throw new Error("bad");
          window.aqToast(t(action === "load" ? "demo.loaded" : "demo.removed"));
          setTimeout(function () { window.location.reload(); }, 700);
        })
        .catch(function () {
          btn.disabled = false;
          window.aqToast(t("demo.failed"));
        });
    });
  }
  ["demo-load", "demo-load-2", "charts-demo"].forEach(function (id) { wireDemo(id, "load"); });
  ["demo-remove"].forEach(function (id) { wireDemo(id, "remove"); });

  /* ---------- officials: status workflow ---------- */
  document.querySelectorAll("[data-status-ward][data-status-code], [data-status-id]").forEach(function (sel) {
    sel.addEventListener("change", function () {
      var payload = {};
      if (sel.hasAttribute("data-status-id")) {
        payload = { id: sel.getAttribute("data-status-id"), status: sel.value };
      } else {
        payload = {
          ward: sel.getAttribute("data-status-ward"),
          code: sel.getAttribute("data-status-code"),
          status: sel.value
        };
      }
      fetch("/officials/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(function (r) { if (!r.ok) throw new Error("bad"); window.aqToast(t("off.status_changed")); })
        .catch(function () { window.aqToast(t("off.status_failed")); });
    });
  });

  /* ---------- language: refresh dynamic nodes ---------- */
  document.addEventListener("aq:lang", function () {
    // Anything rendered after load should re-translate itself here.
    document.querySelectorAll("[data-i18n-dynamic]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key);
    });
    document.dispatchEvent(new CustomEvent("aq:translated"));
  });

  /* initial pass for anything injected before this script ran */
  if (window.AquaI18n) window.AquaI18n.apply();
})();
