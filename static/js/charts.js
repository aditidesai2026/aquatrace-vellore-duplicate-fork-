/* AquaTrace — charts dashboard (Chart.js) */
(function () {
  "use strict";

  if (typeof Chart === "undefined") return;

  function t(key, vars) { return window.aqT ? window.aqT(key, vars) : key; }

  var PALETTE = {
    "Vellore Fort": "#0b3b6f",
    "Sathuvachari": "#0d9488",
    "Shenbakkam": "#0369a1",
    "Katpadi": "#0ea5e9"
  };
  var ZONE_FALLBACK = ["#0b3b6f", "#0d9488", "#0369a1", "#0ea5e9", "#14b8a6", "#0891b2"];
  var SEV_COLOR = {
    CRITICAL: "#e11d48", HIGH: "#ea580c", MEDIUM: "#d97706",
    LOW: "#0284c7", NONE: "#0f9d76"
  };

  var PARAMS = ["ph", "turbidity", "tds", "dissolved_oxygen"];
  var PARAM_LABEL = {
    ph: "term.ph", turbidity: "term.turbidity", tds: "term.tds",
    dissolved_oxygen: "term.dissolved_oxygen"
  };

  /* ---------- limit lines plugin (values come from water_diagnosis.py) ---- */
  var limitLines = {
    id: "limitLines",
    afterDatasetsDraw: function (chart, args, opts) {
      var lines = (opts && opts.lines) || [];
      if (!lines.length) return;
      var yScale = chart.scales.y;
      if (!yScale) return;
      var ctx = chart.ctx;
      var area = chart.chartArea;
      ctx.save();
      lines.forEach(function (line) {
        var y = yScale.getPixelForValue(line.value);
        if (y < area.top || y > area.bottom) return;
        ctx.beginPath();
        ctx.setLineDash([6, 5]);
        ctx.lineWidth = 2;
        ctx.strokeStyle = line.color || "#e11d48";
        ctx.moveTo(area.left, y);
        ctx.lineTo(area.right, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = line.color || "#e11d48";
        ctx.font = "700 11px 'Plus Jakarta Sans', sans-serif";
        ctx.textAlign = "right";
        ctx.textBaseline = "bottom";
        ctx.fillText(line.label, area.right - 4, y - 3);
      });
      ctx.restore();
    }
  };
  Chart.register(limitLines);

  Chart.defaults.font.family = "'Plus Jakarta Sans', 'Noto Sans Tamil', sans-serif";
  Chart.defaults.color = "#0b3b6f";
  Chart.defaults.borderColor = "rgba(255,255,255,.9)";

  var charts = {};
  var data = null;

  var fZone = document.getElementById("c-zone");
  var fGroup = document.getElementById("c-group");
  var fFrom = document.getElementById("c-from");
  var fTo = document.getElementById("c-to");
  var fReset = document.getElementById("c-reset");
  var countEl = document.getElementById("charts-count");
  var emptyBox = document.getElementById("charts-empty");

  function qs() {
    var q = [];
    if (fZone && fZone.value) q.push("zone=" + encodeURIComponent(fZone.value));
    if (fGroup && fGroup.value) q.push("group=" + fGroup.value);
    if (fFrom && fFrom.value) q.push("from=" + fFrom.value);
    if (fTo && fTo.value) q.push("to=" + fTo.value);
    return q.join("&");
  }

  function destroy(id) {
    if (charts[id]) { charts[id].destroy(); delete charts[id]; }
  }

  function baseOptions(unit) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 12, usePointStyle: true, padding: 14 } },
        tooltip: {
          backgroundColor: "rgba(6,40,63,.94)",
          padding: 10, cornerRadius: 10, displayColors: true,
          titleFont: { weight: "700" }
        },
        limitLines: { lines: [] }
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 60, autoSkip: true, maxTicksLimit: 14 } },
        y: {
          beginAtZero: true,
          title: { display: !!unit, text: unit || "" }
        }
      }
    };
  }

  function noData(id) {
    var canvas = document.getElementById(id);
    if (!canvas) return;
    destroy(id);
    var ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#64748b";
    ctx.font = "600 14px 'Plus Jakarta Sans', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(t("charts.no_data"), canvas.width / 2, canvas.height / 2);
  }

  /* ---------- averages with limit lines ---------------------------------- */
  function avgChart(id, param, lines, unit) {
    var rows = (data.avg && data.avg[param]) || [];
    if (!rows.length) return noData(id);
    destroy(id);
    var opts = baseOptions(unit);
    opts.plugins.limitLines.lines = lines;
    opts.plugins.tooltip.callbacks = {
      label: function (c) { return " " + c.parsed.y + " " + unit + " (" + t("charts.readings") + ": " + rows[c.dataIndex].count + ")"; }
    };
    charts[id] = new Chart(document.getElementById(id), {
      type: "bar",
      data: {
        labels: rows.map(function (r) { return r.label; }),
        datasets: [{
          label: t(PARAM_LABEL[param]),
          data: rows.map(function (r) { return r.avg; }),
          backgroundColor: rows.map(function (r) { return outOfRange(param, r.avg) ? "#f59e0b" : "#0ea5e9"; }),
          borderRadius: 8, borderSkipped: false, maxBarThickness: 34
        }]
      },
      options: opts
    });
  }

  var LIMITS = {
    ph: { lines: [{ value: 6.5, label: "6.5", color: "#0f9d76" }, { value: 8.5, label: "8.5", color: "#e11d48" }] },
    turbidity: { lines: [{ value: 1, label: "1 NTU", color: "#0f9d76" }, { value: 5, label: "5 NTU", color: "#e11d48" }] },
    tds: { lines: [{ value: 500, label: "500", color: "#0f9d76" }, { value: 1000, label: "1000", color: "#f59e0b" }, { value: 2000, label: "2000", color: "#e11d48" }] },
    dissolved_oxygen: { lines: [{ value: 4, label: "4 mg/L", color: "#0f9d76" }, { value: 2, label: "2 mg/L", color: "#e11d48" }] }
  };

  function outOfRange(param, v) {
    if (v === null || v === undefined) return false;
    if (param === "ph") return v < 6.5 || v > 8.5;
    if (param === "turbidity") return v > 1;
    if (param === "tds") return v > 500;
    return v < 4;
  }

  /* ---------- lines over time, one per zone ------------------------------ */
  function lineChart(id, param, unit) {
    var series = data.series || {};
    var zones = Object.keys(series);
    if (!zones.length || !zones.some(function (z) { return series[z].length; })) return noData(id);
    destroy(id);

    var dates = {};
    zones.forEach(function (z) {
      series[z].forEach(function (p) { dates[p.date] = true; });
    });
    var labels = Object.keys(dates).sort();

    var datasets = zones.map(function (z, i) {
      var byDate = {};
      series[z].forEach(function (p) { byDate[p.date] = p[param]; });
      return {
        label: z,
        data: labels.map(function (d) { return byDate[d] === undefined ? null : byDate[d]; }),
        borderColor: PALETTE[z] || ZONE_FALLBACK[i % ZONE_FALLBACK.length],
        backgroundColor: PALETTE[z] || ZONE_FALLBACK[i % ZONE_FALLBACK.length],
        tension: 0.35, spanGaps: true, borderWidth: 2.5,
        pointRadius: 3, pointHoverRadius: 6
      };
    });

    var opts = baseOptions(unit);
    opts.plugins.limitLines.lines = LIMITS[param].lines;
    opts.interaction.mode = "nearest";
    charts[id] = new Chart(document.getElementById(id), {
      type: "line",
      data: { labels: labels, datasets: datasets },
      options: opts
    });
  }

  /* ---------- histograms -------------------------------------------------- */
  function histChart(id, param, unit) {
    var h = data.hist && data.hist[param];
    if (!h || !h.buckets || !h.buckets.some(function (b) { return b.count > 0; })) return noData(id);
    destroy(id);
    var opts = baseOptions(t("charts.readings"));
    opts.plugins.legend.display = false;
    opts.plugins.tooltip.callbacks = {
      title: function (items) {
        var b = h.buckets[items[0].dataIndex];
        return b.from + " – " + b.to + " " + unit;
      },
      label: function (c) { return " " + c.parsed.y + " " + t("charts.readings"); }
    };
    opts.scales.x.title = { display: true, text: unit };
    charts[id] = new Chart(document.getElementById(id), {
      type: "bar",
      data: {
        labels: h.buckets.map(function (b) { return b.from + "–" + b.to; }),
        datasets: [{
          label: t(PARAM_LABEL[param]),
          data: h.buckets.map(function (b) { return b.count; }),
          backgroundColor: "#0ea5e9", borderRadius: 6, borderSkipped: false
        }]
      },
      options: opts
    });
  }

  /* ---------- scatter, coloured by severity ------------------------------ */
  function scatterChart(id, points) {
    if (!points || !points.length) return noData(id);
    destroy(id);
    var bySev = {};
    points.forEach(function (p) {
      (bySev[p.severity] = bySev[p.severity] || []).push({ x: p.x, y: p.y });
    });
    var opts = baseOptions("");
    opts.interaction.mode = "nearest";
    opts.plugins.legend.labels.usePointStyle = true;
    opts.scales.x.title = { display: true, text: "pH" };
    opts.scales.y.beginAtZero = false;
    opts.plugins.tooltip.callbacks = {
      label: function (c) {
        return " pH " + c.parsed.x + " · " + c.parsed.y + " · " + c.dataset.label;
      }
    };
    charts[id] = new Chart(document.getElementById(id), {
      type: "scatter",
      data: {
        datasets: Object.keys(bySev).map(function (sev) {
          return {
            label: t("severity." + sev.toLowerCase()),
            data: bySev[sev],
            backgroundColor: (SEV_COLOR[sev] || "#0284c7") + "cc",
            borderColor: SEV_COLOR[sev] || "#0284c7",
            pointRadius: 5, pointHoverRadius: 8
          };
        })
      },
      options: opts
    });
  }

  /* ---------- severity + problems ---------------------------------------- */
  function severityChart() {
    var id = "chart-severity";
    var counts = data.severity || {};
    var keys = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"];
    if (!keys.some(function (k) { return counts[k]; })) return noData(id);
    destroy(id);
    var opts = baseOptions(t("charts.readings"));
    opts.plugins.legend.display = false;
    opts.plugins.tooltip.callbacks = {
      label: function (c) {
        var sev = keys[c.dataIndex];
        var icon = (sev === "CRITICAL" || sev === "HIGH") ? "✕ " : (sev === "MEDIUM" ? "! " : (sev === "LOW" ? "〜 " : "✓ "));
        return " " + icon + sev + ": " + c.parsed.y;
      }
    };
    charts[id] = new Chart(document.getElementById(id), {
      type: "bar",
      data: {
        labels: keys.map(function (k) { return t("severity." + k.toLowerCase()); }),
        datasets: [{
          data: keys.map(function (k) { return counts[k] || 0; }),
          backgroundColor: keys.map(function (k) { return SEV_COLOR[k]; }),
          borderRadius: 8, borderSkipped: false, maxBarThickness: 46
        }]
      },
      options: opts
    });
  }

  function problemsChart() {
    var id = "chart-problems";
    var counts = data.problems || {};
    var keys = Object.keys(counts).filter(function (k) { return counts[k] > 0; })
      .sort(function (a, b) { return counts[b] - counts[a]; });
    if (!keys.length) return noData(id);
    destroy(id);
    var opts = baseOptions(t("charts.readings"));
    opts.indexAxis = "y";
    opts.plugins.legend.display = false;
    opts.scales.x.title = { display: true, text: t("charts.readings") };
    opts.plugins.tooltip.callbacks = {
      label: function (c) { return " " + c.parsed.x + " " + t("charts.readings"); }
    };
    charts[id] = new Chart(document.getElementById(id), {
      type: "bar",
      data: {
        labels: keys.map(function (k) { return t("report." + k); }),
        datasets: [{
          data: keys.map(function (k) { return counts[k]; }),
          backgroundColor: "#0d9488", borderRadius: 8, borderSkipped: false, maxBarThickness: 26
        }]
      },
      options: opts
    });
  }

  function dayZoneChart() {
    var id = "chart-dayzone";
    var dayZone = data.day_zone || {};
    var dates = Object.keys(dayZone).sort();
    if (!dates.length) return noData(id);
    destroy(id);
    var zones = {};
    dates.forEach(function (d) {
      Object.keys(dayZone[d]).forEach(function (z) { zones[z] = true; });
    });
    zones = Object.keys(zones).sort();

    var opts = baseOptions(t("charts.readings"));
    opts.scales.x.stacked = true;
    opts.scales.y.stacked = true;
    opts.plugins.tooltip.callbacks = {
      label: function (c) {
        return " " + c.dataset.label + ": " + c.parsed.y + " " + t("charts.readings");
      }
    };
    charts[id] = new Chart(document.getElementById(id), {
      type: "bar",
      data: {
        labels: dates,
        datasets: zones.map(function (z, i) {
          return {
            label: z,
            data: dates.map(function (d) { return (dayZone[d] && dayZone[d][z]) || 0; }),
            backgroundColor: PALETTE[z] || ZONE_FALLBACK[i % ZONE_FALLBACK.length],
            borderRadius: 4, borderSkipped: false
          };
        })
      },
      options: opts
    });
  }

  /* ---------- ward × parameter heatmap (HTML table) ----------------------- */
  function renderHeatmap() {
    var host = document.getElementById("heatmap");
    if (!host) return;
    var rows = (data.ward_matrix || []).slice(0, 24);
    if (!rows.length) { host.innerHTML = '<p class="text-sm text-ink/60">' + t("charts.no_data") + "</p>"; return; }
    var cols = [
      ["ph", "term.ph"], ["turbidity", "term.turbidity"],
      ["tds", "term.tds"], ["dissolved_oxygen", "term.dissolved_oxygen"]
    ];
    var html = '<table class="table-glass"><thead><tr><th>' + t("check.ward") +
      "</th><th>" + t("filter.zone") + "</th>" +
      cols.map(function (c) { return "<th>" + t(c[1]) + "</th>"; }).join("") +
      "<th>" + t("charts.readings") + "</th></tr></thead><tbody>";
    rows.forEach(function (r) {
      html += "<tr><td class='font-bold'>" + r.ward + "</td><td>" + r.zone + "</td>";
      cols.forEach(function (c) {
        var n = r[c[0]] || 0;
        var ratio = r.total ? n / r.total : 0;
        var bg = n === 0 ? "rgba(255,255,255,.7)"
          : "rgba(225,29,72," + (0.12 + ratio * 0.65).toFixed(2) + ")";
        var mark = n === 0 ? "✓" : "✕";
        html += "<td style='background:" + bg + "'><span aria-hidden='true'>" + mark +
          "</span> " + n + "</td>";
      });
      html += "<td>" + r.total + "</td></tr>";
    });
    html += "</tbody></table>";
    host.innerHTML = html;
  }

  /* ---------- My history (browser storage, no login) --------------------- */
  function myHistory() {
    var list = [];
    try { list = JSON.parse(localStorage.getItem("aquatrace_history") || "[]"); } catch (e) { list = []; }
    var empty = document.getElementById("history-empty");
    var grid = document.getElementById("history-charts");
    if (!list.length) {
      if (empty) empty.classList.remove("hidden");
      if (grid) grid.hidden = true;
      return;
    }
    if (empty) empty.classList.add("hidden");
    if (grid) grid.hidden = false;

    var labels = list.map(function (r) { return r.at.slice(0, 10); });
    [
      ["chart-my-ph", "ph", "pH", true],
      ["chart-my-turbidity", "turbidity", "NTU", true],
      ["chart-my-tds", "tds", "mg/L", true],
      ["chart-my-do", "dissolved_oxygen", "mg/L", true]
    ].forEach(function (spec) {
      var id = spec[0], key = spec[1], unit = spec[2], showLimits = spec[3];
      var vals = list.map(function (r) { return r[key]; });
      if (!vals.some(function (v) { return v !== null && v !== undefined; })) return noData(id);
      destroy(id);
      var opts = baseOptions(unit);
      opts.plugins.limitLines.lines = showLimits ? LIMITS[key].lines : [];
      opts.plugins.tooltip.callbacks = {
        label: function (c) { return " " + c.parsed.y + " " + unit; }
      };
      charts[id] = new Chart(document.getElementById(id), {
        type: "line",
        data: {
          labels: labels,
          datasets: [{
            label: t(PARAM_LABEL[key]),
            data: vals,
            borderColor: "#0d9488",
            backgroundColor: "rgba(13,148,136,.15)",
            fill: true, tension: 0.3, borderWidth: 2.5,
            pointRadius: 4, pointHoverRadius: 7, spanGaps: true
          }]
        },
        options: opts
      });
    });
  }

  /* ---------- download a chart ------------------------------------------- */
  document.querySelectorAll("[data-download]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-download");
      if (id === "heatmap") return downloadHeatmapCsv();
      var chart = charts[id];
      if (!chart) return window.aqToast(t("charts.no_data"));
      var link = document.createElement("a");
      link.download = "aquatrace-" + id + ".png";
      link.href = chart.toBase64Image();
      link.click();
    });
  });

  function downloadHeatmapCsv() {
    var rows = data.ward_matrix || [];
    if (!rows.length) return window.aqToast(t("charts.no_data"));
    var lines = ["ward,zone,total,ph,turbidity,tds,dissolved_oxygen"];
    rows.forEach(function (r) {
      lines.push([r.ward, r.zone, r.total, r.ph, r.turbidity, r.tds, r.dissolved_oxygen].join(","));
    });
    var blob = new Blob([lines.join("\n")], { type: "text/csv" });
    var link = document.createElement("a");
    link.download = "aquatrace-ward-heatmap.csv";
    link.href = URL.createObjectURL(blob);
    link.click();
    setTimeout(function () { URL.revokeObjectURL(link.href); }, 2000);
  }

  /* ---------- load everything -------------------------------------------- */
  function render() {
    avgChart("chart-avg-ph", "ph", LIMITS.ph.lines, "pH");
    avgChart("chart-avg-turbidity", "turbidity", LIMITS.turbidity.lines, "NTU");
    avgChart("chart-avg-tds", "tds", LIMITS.tds.lines, "mg/L");
    avgChart("chart-avg-do", "dissolved_oxygen", LIMITS.dissolved_oxygen.lines, "mg/L");

    lineChart("chart-line-ph", "ph", "pH");
    lineChart("chart-line-turbidity", "turbidity", "NTU");
    lineChart("chart-line-tds", "tds", "mg/L");
    lineChart("chart-line-do", "dissolved_oxygen", "mg/L");

    histChart("chart-hist-ph", "ph", "pH");
    histChart("chart-hist-turbidity", "turbidity", "NTU");
    histChart("chart-hist-tds", "tds", "mg/L");
    histChart("chart-hist-do", "dissolved_oxygen", "mg/L");

    scatterChart("chart-scatter-tds", data.scatter);
    scatterChart("chart-scatter-turbidity", data.scatter_turbidity);

    severityChart();
    problemsChart();
    dayZoneChart();
    renderHeatmap();
    myHistory();
  }

  function load() {
    if (countEl) countEl.textContent = t("common.loading");
    fetch("/api/charts" + (qs() ? "?" + qs() : ""))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        data = d;
        if (countEl) countEl.textContent = t("charts.count", { n: d.count });
        if (emptyBox) emptyBox.classList.toggle("hidden", d.count > 0);
        render();
      })
      .catch(function () {
        if (countEl) countEl.textContent = t("error.generic");
      });
  }

  [fZone, fGroup, fFrom, fTo].forEach(function (el) {
    if (el) el.addEventListener("change", load);
  });
  if (fReset) {
    fReset.addEventListener("click", function () {
      if (fZone) fZone.value = "";
      if (fGroup) fGroup.value = "ward";
      if (fFrom) fFrom.value = "";
      if (fTo) fTo.value = "";
      load();
    });
  }

  var clearBtn = document.getElementById("history-clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      try { localStorage.removeItem("aquatrace_history"); } catch (e) { /* ignore */ }
      window.aqToast(t("charts.cleared"));
      myHistory();
    });
  }

  document.addEventListener("aq:lang", function () {
    if (data) render();
  });

  load();
})();
