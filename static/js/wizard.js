/* AquaTrace — reporting wizard (one question per screen) */
(function () {
  "use strict";

  var TOTAL = 6;
  var current = 1;
  var skippedDO = false;

  var form = document.getElementById("wizard");
  if (!form) return;

  var steps = Array.prototype.slice.call(document.querySelectorAll(".wizard-step"));
  var btnBack = document.getElementById("btn-back");
  var btnNext = document.getElementById("btn-next");
  var btnSubmit = document.getElementById("btn-submit");
  var stepCurrent = document.getElementById("step-current");
  var stepTitle = document.getElementById("step-title");
  var progress = document.getElementById("progress");
  var progressFill = document.getElementById("progress-fill");
  var dots = document.getElementById("step-dots").children;
  var formError = document.getElementById("form-error");

  var STEP_TITLE_KEYS = {
    1: "check.ph.title",
    2: "check.turbidity.title",
    3: "check.tds.title",
    4: "check.do.title",
    5: "check.notice.title",
    6: "check.location.title"
  };

  /* ---------- limits: single source of truth on the server ---------- */
  var LIMITS = {
    ph: { ok: [6.5, 8.5], watch: [6.0, 9.0] },
    turbidity: { ok: 1, watch: 5 },
    tds: { ok: 500, watch: 2000 },
    dissolved_oxygen: { ok: 4, watch: 2 }
  };
  fetch("/api/limits").then(function (r) { return r.json(); }).then(function (L) {
    LIMITS.ph = { ok: [L.ph.accept_min, L.ph.accept_max], watch: [L.ph.watch_min, L.ph.watch_max] };
    LIMITS.turbidity = { ok: L.turbidity.acceptable, watch: L.turbidity.problem };
    LIMITS.tds = { ok: L.tds.acceptable, watch: L.tds.permissible };
    LIMITS.dissolved_oxygen = { ok: L.dissolved_oxygen.warning, watch: L.dissolved_oxygen.very_low };
    ["ph", "turbidity", "tds", "dissolved_oxygen"].forEach(function (k) { updateGauge(k); });
  }).catch(function () { /* keep the defaults, they mirror water_diagnosis.py */ });

  /* ---------- state helpers ---------- */
  function t(key, vars) { return window.aqT ? window.aqT(key, vars) : key; }

  function stateOf(key, v) {
    if (v === null || v === "" || isNaN(v)) return "none";
    var L = LIMITS[key];
    if (key === "ph") {
      if (v >= L.ok[0] && v <= L.ok[1]) return "ok";
      if (v >= L.watch[0] && v <= L.watch[1]) return "watch";
      return "unsafe";
    }
    if (key === "turbidity" || key === "tds") {
      if (v <= L.ok) return "ok";
      if (v <= L.watch) return "watch";
      return "unsafe";
    }
    // dissolved oxygen: higher is better (project rule)
    if (v >= L.ok) return "ok";
    if (v >= L.watch) return "watch";
    return "unsafe";
  }

  var SCALE = { ph: 14, turbidity: 20, tds: 3000, dissolved_oxygen: 14 };
  var GRADIENT = {
    ph: "linear-gradient(90deg,#fca5a5 0%,#fde68a 25%,#6ee7b7 50%,#fde68a 75%,#fca5a5 100%)",
    turbidity: "linear-gradient(90deg,#6ee7b7 0%,#6ee7b7 5%,#fde68a 25%,#fca5a5 100%)",
    tds: "linear-gradient(90deg,#6ee7b7 0%,#6ee7b7 17%,#fde68a 67%,#fca5a5 100%)",
    dissolved_oxygen: "linear-gradient(90deg,#fca5a5 0%,#fde68a 29%,#6ee7b7 57%,#6ee7b7 100%)"
  };
  var STATE_LABEL = { ok: "gauge.ok", watch: "gauge.watch", unsafe: "gauge.unsafe", none: "gauge.none" };
  var STATE_ICON = { ok: "✓", watch: "!", unsafe: "✕", none: "–" };

  function updateGauge(key) {
    var input = document.getElementById("in-" + key);
    var gauge = document.getElementById("gauge-" + key);
    if (!input || !gauge) return;
    var raw = input.value;
    var v = raw === "" ? null : parseFloat(raw);
    var state = stateOf(key, v === null || isNaN(v) ? null : v);

    gauge.style.background = GRADIENT[key];
    var marker = document.getElementById("marker-" + key);
    if (marker) {
      var pos = 0;
      if (v !== null && !isNaN(v)) pos = Math.max(0, Math.min(1, v / SCALE[key])) * 100;
      marker.style.left = pos + "%";
      marker.style.opacity = v === null || isNaN(v) ? "0" : "1";
    }
    var pill = document.getElementById("state-" + key);
    if (pill) {
      pill.className = "state-pill state-" + state;
      pill.textContent = STATE_ICON[state] + " " + t(STATE_LABEL[state]);
      pill.setAttribute("data-i18n-dynamic", "1");
      pill.setAttribute("data-i18n", STATE_LABEL[state]);
      pill.textContent = STATE_ICON[state] + " " + t(STATE_LABEL[state]);
    }
  }

  /* ---------- validation ---------- */
  var RULES = {
    ph: { min: 0, max: 14, required: true },
    turbidity: { min: 0, max: 1e6, required: true },
    tds: { min: 0, max: 50000, required: true },
    dissolved_oxygen: { min: 0, max: 20, required: false }
  };

  function validateField(key) {
    var input = document.getElementById("in-" + key);
    var err = document.getElementById("err-" + key);
    if (!input || !err) return true;
    var rule = RULES[key];
    var raw = input.value.trim();
    var msg = "";

    if (raw === "") {
      if (rule.required && !(key === "dissolved_oxygen" && skippedDO)) msg = t("error.required");
    } else {
      var v = parseFloat(raw);
      if (isNaN(v)) msg = t("error.not_a_number");
      else if (v < rule.min) msg = t("error.too_low");
      else if (v > rule.max) msg = t("error.too_high");
    }

    if (msg) {
      err.textContent = msg;
      err.hidden = false;
      input.classList.add("input-error");
      input.setAttribute("aria-invalid", "true");
      return false;
    }
    err.hidden = true;
    input.classList.remove("input-error");
    input.removeAttribute("aria-invalid");
    return true;
  }

  /* ---------- number + slider wiring ---------- */
  ["ph", "turbidity", "tds", "dissolved_oxygen"].forEach(function (key) {
    var input = document.getElementById("in-" + key);
    var slider = document.getElementById("range-" + key);
    if (!input || !slider) return;

    input.addEventListener("input", function () {
      if (input.value !== "") {
        var v = parseFloat(input.value);
        if (!isNaN(v)) slider.value = Math.max(slider.min, Math.min(slider.max, v));
      }
      updateGauge(key);
      validateField(key);
    });
    input.addEventListener("blur", function () { validateField(key); });

    slider.addEventListener("input", function () {
      input.value = slider.value;
      updateGauge(key);
      validateField(key);
    });

    updateGauge(key);
  });

  var skipBtn = document.getElementById("skip-do");
  if (skipBtn) {
    skipBtn.addEventListener("click", function () {
      skippedDO = true;
      var input = document.getElementById("in-dissolved_oxygen");
      if (input) { input.value = ""; input.classList.remove("input-error"); }
      var err = document.getElementById("err-dissolved_oxygen");
      if (err) err.hidden = true;
      go(5);
    });
  }

  /* ---------- step navigation ---------- */
  function stepValid(n) {
    if (n === 1) return validateField("ph");
    if (n === 2) return validateField("turbidity");
    if (n === 3) return validateField("tds");
    if (n === 4) return (skippedDO || validateField("dissolved_oxygen"));
    return true;
  }

  function go(n) {
    current = Math.max(1, Math.min(TOTAL, n));
    steps.forEach(function (s) {
      var isActive = parseInt(s.getAttribute("data-step"), 10) === current;
      s.hidden = !isActive;
    });
    stepCurrent.textContent = current;
    stepTitle.setAttribute("data-i18n", STEP_TITLE_KEYS[current]);
    stepTitle.textContent = t(STEP_TITLE_KEYS[current]);
    stepTitle.setAttribute("data-i18n-dynamic", "1");

    var pct = (current / TOTAL) * 100;
    progressFill.style.width = pct + "%";
    progress.setAttribute("aria-valuenow", String(current));
    for (var i = 0; i < dots.length; i++) {
      dots[i].className = i + 1 < current ? "done" : (i + 1 === current ? "on" : "");
    }

    btnBack.hidden = current === 1;
    btnNext.hidden = current === TOTAL;
    btnSubmit.hidden = current !== TOTAL;
    if (current === 6) initMapStep();
    if (formError) formError.hidden = true;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  btnNext.addEventListener("click", function () {
    if (!stepValid(current)) {
      var firstErr = document.querySelector(".wizard-step:not([hidden]) .error-text:not([hidden])");
      if (firstErr) firstErr.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    go(current + 1);
  });
  btnBack.addEventListener("click", function () { go(current - 1); });

  /* ---------- zone / ward dropdowns ---------- */
  var zoneSel = document.getElementById("in-zone");
  var wardSel = document.getElementById("in-ward");
  var AREAS = window.AQUATRACE_AREAS || { zones: [], wards: {} };

  function fillWards(zone) {
    if (!wardSel) return;
    var list = AREAS.wards[zone] || [];
    wardSel.innerHTML = "";
    list.forEach(function (w, i) {
      var opt = document.createElement("option");
      opt.value = w;
      opt.textContent = w;
      if (i === 0) opt.selected = true;
      wardSel.appendChild(opt);
    });
  }
  if (zoneSel) {
    zoneSel.addEventListener("change", function () { fillWards(zoneSel.value); });
  }

  /* ---------- geolocation (Vellore only) ---------- */
  var outsideBox = document.getElementById("outside-vellore");
  var locStatus = document.getElementById("location-status");
  var mapBox = document.getElementById("map-pick");
  var pickMap = null;
  var pickMarker = null;
  var bounds = AREAS.bounds || [[12.85, 79.05], [13.0, 79.2]];
  var picked = null;

  function initMapStep() {
    if (pickMap || !mapBox || typeof L === "undefined") return;
    mapBox.classList.remove("hidden");
    pickMap = L.map("map-pick", { zoomControl: true, attributionControl: true })
      .setView(AREAS.center || [12.9236, 79.132], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 17,
      minZoom: 11,
      attribution: "© OpenStreetMap"
    }).addTo(pickMap);
    pickMap.setMaxBounds([[bounds[0][0] - 0.08, bounds[0][1] - 0.08],
                          [bounds[1][0] + 0.08, bounds[1][1] + 0.08]]);
    pickMarker = L.marker(AREAS.center || [12.9236, 79.132], { draggable: true }).addTo(pickMap);
    pickMarker.on("dragend", function () {
      var ll = pickMarker.getLatLng();
      handlePoint(ll.lat, ll.lng, false);
    });
    setTimeout(function () { pickMap.invalidateSize(); }, 200);
  }

  function handlePoint(lat, lon, moveMarker) {
    var inside = lat >= bounds[0][0] && lat <= bounds[1][0] &&
                 lon >= bounds[0][1] && lon <= bounds[1][1];
    if (!inside) {
      if (outsideBox) outsideBox.classList.remove("hidden");
      if (locStatus) locStatus.textContent = t("check.location_none");
      picked = null;
      return false;
    }
    if (outsideBox) outsideBox.classList.add("hidden");
    picked = { latitude: lat, longitude: lon };
    if (moveMarker && pickMarker) pickMarker.setLatLng([lat, lon]);
    if (locStatus) locStatus.textContent = t("check.location_ok");
    // Suggest the closest ward (the server confirms it).
    var best = null, bestD = null;
    Object.keys(AREAS.centroids || {}).forEach(function (zone) {
      var byWard = AREAS.centroids[zone];
      Object.keys(byWard).forEach(function (ward) {
        var c = byWard[ward];
        var d = Math.pow(c[0] - lat, 2) + Math.pow(c[1] - lon, 2);
        if (bestD === null || d < bestD) { bestD = d; best = { zone: zone, ward: ward }; }
      });
    });
    if (best && zoneSel && wardSel) {
      zoneSel.value = best.zone;
      fillWards(best.zone);
      wardSel.value = best.ward;
    }
    return true;
  }

  var locBtn = document.getElementById("use-location");
  if (locBtn) {
    locBtn.addEventListener("click", function () {
      initMapStep();
      if (!navigator.geolocation) {
        if (outsideBox) outsideBox.classList.remove("hidden");
        return;
      }
      if (locStatus) locStatus.textContent = t("common.loading");
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          handlePoint(pos.coords.latitude, pos.coords.longitude, true);
        },
        function () {
          if (locStatus) locStatus.textContent = t("check.location_none");
          if (outsideBox) outsideBox.classList.remove("hidden");
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  }

  /* ---------- submit ---------- */
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();

    var fd = new FormData(form);
    if (picked) {
      fd.set("latitude", String(picked.latitude));
      fd.set("longitude", String(picked.longitude));
    }
    // reports come as multiple checkboxes; FormData already collects them
    if (skippedDO) fd.delete("dissolved_oxygen");
    fd.set("zone", zoneSel ? zoneSel.value : AREAS.defaultZone);
    fd.set("ward", wardSel ? wardSel.value : "");

    btnSubmit.disabled = true;
    btnSubmit.textContent = t("common.loading");

    fetch("/api/readings", { method: "POST", body: fd })
      .then(function (r) {
        return r.json().then(function (d) { return { status: r.status, data: d }; });
      })
      .then(function (res) {
        if (!res.data.ok) throw res.data;
        saveHistory(fd, res.data);
        window.aqToast(t("charts.saved"));
        window.location.href = res.data.redirect;
      })
      .catch(function (err) {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = '<span>' + t("check.submit") + '</span> <span aria-hidden="true">✓</span>';
        var msg = t("error.generic");
        if (err && err.outside_vellore) msg = t("check.outside");
        else if (err && err.errors) {
          var first = Object.keys(err.errors)[0];
          msg = t(err.errors[first]);
          var field = document.getElementById("in-" + first);
          if (field) {
            field.classList.add("input-error");
            var e = document.getElementById("err-" + first);
            if (e) { e.textContent = msg; e.hidden = false; }
            field.scrollIntoView({ behavior: "smooth", block: "center" });
          }
        }
        if (formError) {
          formError.textContent = msg;
          formError.hidden = false;
        }
      });
  });

  /* ---------- "My history" lives in this browser only ---------- */
  function saveHistory(fd, data) {
    try {
      var key = "aquatrace_history";
      var list = JSON.parse(localStorage.getItem(key) || "[]");
      list.push({
        id: data.id,
        at: new Date().toISOString(),
        ph: parseFloat(fd.get("ph")),
        turbidity: parseFloat(fd.get("turbidity")),
        tds: parseFloat(fd.get("tds")),
        dissolved_oxygen: fd.get("dissolved_oxygen") ? parseFloat(fd.get("dissolved_oxygen")) : null,
        zone: fd.get("zone"),
        ward: fd.get("ward"),
        severity: data.status
      });
      localStorage.setItem(key, JSON.stringify(list.slice(-200)));
    } catch (e) { /* private mode: history simply is not saved */ }
  }

  document.addEventListener("aq:lang", function () {
    stepTitle.textContent = t(STEP_TITLE_KEYS[current]);
    ["ph", "turbidity", "tds", "dissolved_oxygen"].forEach(updateGauge);
  });

  go(1);
})();
