/* AquaTrace — community map (Leaflet), ward-level pins only */
(function () {
  "use strict";

  var mapEl = document.getElementById("map");
  if (!mapEl || typeof L === "undefined") return;

  function t(key, vars) { return window.aqT ? window.aqT(key, vars) : key; }

  var CENTER = [12.9236, 79.132];       // Vellore (~12.92 N, 79.13 E)
  var BOUNDS = [[12.85, 79.05], [13.0, 79.20]];  // Vellore only
  var SEV_COLOR = {
    CRITICAL: "#e11d48", HIGH: "#ea580c", MEDIUM: "#d97706",
    LOW: "#0284c7", NONE: "#0f9d76"
  };
  var SEV_ICON = { CRITICAL: "✕", HIGH: "✕", MEDIUM: "!", LOW: "〜", NONE: "✓" };
  var SEV_CLASS = {
    CRITICAL: "badge-red", HIGH: "badge-red", MEDIUM: "badge-amber",
    LOW: "badge-blue", NONE: "badge-green"
  };

  var map = L.map("map", {
    center: CENTER, zoom: 12, minZoom: 11, maxZoom: 17,
    maxBounds: [[BOUNDS[0][0] - 0.1, BOUNDS[0][1] - 0.1], [BOUNDS[1][0] + 0.1, BOUNDS[1][1] + 0.1]],
    maxBoundsViscosity: 0.8,
    scrollWheelZoom: false
  });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 17, attribution: "© OpenStreetMap contributors"
  }).addTo(map);

  var layer = L.layerGroup().addTo(map);
  var lastData = null;

  var fZone = document.getElementById("f-zone");
  var fSev = document.getElementById("f-severity");
  var fProblem = document.getElementById("f-problem");
  var fFrom = document.getElementById("f-from");
  var fTo = document.getElementById("f-to");
  var fReset = document.getElementById("f-reset");
  var loading = document.getElementById("map-loading");
  var emptyBox = document.getElementById("map-empty");
  var table = document.getElementById("ward-table");
  var tbody = document.getElementById("ward-table-body");
  var countEl = document.getElementById("map-count");

  /* Read ?zone=&ward= from links (officials "view on map") */
  var params = new URLSearchParams(window.location.search);
  if (params.get("zone") && fZone) fZone.value = params.get("zone");
  if (params.get("severity") && fSev) fSev.value = params.get("severity");

  function queryString() {
    var q = [];
    if (fZone && fZone.value) q.push("zone=" + encodeURIComponent(fZone.value));
    if (fSev && fSev.value) q.push("severity=" + encodeURIComponent(fSev.value));
    if (fProblem && fProblem.value) q.push("problem=" + encodeURIComponent(fProblem.value));
    if (fFrom && fFrom.value) q.push("from=" + fFrom.value);
    if (fTo && fTo.value) q.push("to=" + fTo.value);
    return q.join("&");
  }

  function markerFor(ward) {
    var color = SEV_COLOR[ward.worst_severity] || SEV_COLOR.NONE;
    var radius = Math.min(22, 10 + Math.log(ward.count + 1) * 5);
    var m = L.circleMarker([ward.lat, ward.lon], {
      radius: radius,
      color: "#ffffff", weight: 2,
      fillColor: color, fillOpacity: 0.9,
      className: "at-marker"
    });
    m.bindPopup(popupHtml(ward), { maxWidth: 320, minWidth: 220 });
    m.bindTooltip(ward.ward + " · " + ward.count, { direction: "top", offset: [0, -8] });
    return m;
  }

  function popupHtml(ward) {
    var rows = ward.reports.slice(0, 6).map(function (r) {
      var findings = (r.findings || []).map(function (code) {
        return '<li class="text-xs">• <span data-i18n="f.' + code + '.title">' +
          t("f." + code + ".title") + "</span></li>";
      }).join("");
      var notices = (r.reports || []).map(function (x) { return t("report." + x); }).join(", ");
      return '<div class="glass-inset p-2 mb-2">' +
        '<div class="flex items-center gap-2 flex-wrap">' +
        '<span class="badge ' + (SEV_CLASS[r.severity] || "badge-ghost") + '">' +
        SEV_ICON[r.severity] + " " + r.severity + "</span>" +
        '<span class="badge badge-ghost">' + r.status + "</span>" +
        '<span class="text-[11px] text-ink/60">' + r.created_at.slice(0, 16) + "</span>" +
        (r.is_demo ? '<span class="badge badge-amber">DEMO</span>' : "") +
        "</div>" +
        '<p class="text-xs mt-1 font-semibold">pH ' + r.ph + " · " + r.turbidity +
        " NTU · " + r.tds + " mg/L" +
        (r.dissolved_oxygen !== null && r.dissolved_oxygen !== undefined
          ? " · DO " + r.dissolved_oxygen : "") + "</p>" +
        (notices ? '<p class="text-xs text-ink/60">' + notices + "</p>" : "") +
        "<ul>" + findings + "</ul>" +
        "</div>";
    }).join("");

    var more = ward.reports.length > 6
      ? '<p class="text-xs text-ink/60">+' + (ward.reports.length - 6) + "</p>" : "";

    return '<div class="p-1">' +
      '<div class="flex items-center gap-2 flex-wrap mb-2">' +
      '<strong class="text-deep">' + ward.ward + "</strong>" +
      '<span class="badge badge-ghost">' + ward.zone + "</span>" +
      '<span class="badge ' + (SEV_CLASS[ward.worst_severity] || "badge-ghost") + '">' +
      SEV_ICON[ward.worst_severity] + " " + ward.worst_severity + "</span>" +
      '<span class="badge badge-blue">' + ward.count + "</span>" +
      "</div>" + rows + more +
      '<a class="text-xs font-bold text-aqua" href="/check">' +
      t("home.cta") + " →</a></div>";
  }

  function renderTable(wards) {
    if (!tbody) return;
    tbody.innerHTML = wards.map(function (w) {
      var codes = Object.keys(w.codes || {}).map(function (c) {
        return '<span class="badge badge-ghost mb-1" data-i18n="f.' + c + '.title">' +
          t("f." + c + ".title") + "</span>";
      }).join(" ");
      return "<tr>" +
        "<td>" + w.zone + "</td>" +
        '<td class="font-bold">' + w.ward + "</td>" +
        "<td>" + w.count + "</td>" +
        '<td><span class="badge ' + (SEV_CLASS[w.worst_severity] || "badge-ghost") + '">' +
        SEV_ICON[w.worst_severity] + " " + w.worst_severity + "</span></td>" +
        "<td>" + w.latest.slice(0, 10) + "</td>" +
        "<td>" + codes + "</td>" +
        "<td>" + w.worst_status + "</td>" +
        "</tr>";
    }).join("");
  }

  function load() {
    if (loading) loading.classList.remove("hidden");
    if (emptyBox) emptyBox.classList.add("hidden");
    var qs = queryString();
    fetch("/api/map" + (qs ? "?" + qs : ""))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        lastData = data;
        if (loading) loading.classList.add("hidden");
        layer.clearLayers();
        data.wards.forEach(function (w) { layer.addLayer(markerFor(w)); });

        var totalReports = data.wards.reduce(function (a, w) { return a + w.count; }, 0);
        if (countEl) {
          countEl.textContent = t("map.count", { n: totalReports, w: data.wards.length });
        }
        if (table) table.hidden = data.wards.length === 0;
        if (tbody) renderTable(data.wards);
        if (!data.wards.length && emptyBox) emptyBox.classList.remove("hidden");

        if (data.wards.length) {
          var group = L.featureGroup(data.wards.map(function (w) {
            return L.marker([w.lat, w.lon]);
          }));
          map.fitBounds(group.getBounds().pad(0.25), { maxZoom: 14 });
        }
      })
      .catch(function () {
        if (loading) loading.textContent = t("error.generic");
      });
  }

  [fZone, fSev, fProblem, fFrom, fTo].forEach(function (el) {
    if (el) el.addEventListener("change", load);
  });
  if (fReset) {
    fReset.addEventListener("click", function () {
      if (fZone) fZone.value = "";
      if (fSev) fSev.value = "";
      if (fProblem) fProblem.value = "";
      if (fFrom) fFrom.value = "";
      if (fTo) fTo.value = "";
      load();
    });
  }

  document.addEventListener("aq:lang", function () {
    if (lastData) {
      layer.clearLayers();
      lastData.wards.forEach(function (w) { layer.addLayer(markerFor(w)); });
      renderTable(lastData.wards);
      map.closePopup();
    }
  });

  load();
})();
