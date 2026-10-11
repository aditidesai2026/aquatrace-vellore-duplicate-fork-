/* AquaTrace — result page: copy / send the pre-filled VCMC report */
(function () {
  "use strict";

  var R = window.AQUATRACE_RESULT;
  var area = document.getElementById("report-message");
  if (!R) return;

  function t(key) { return window.aqT ? window.aqT(key) : key; }

  var SEV_LABEL = {
    sewage: "f.sewage.title", acid_industrial: "f.acid_industrial.title",
    corrosive_soft: "f.corrosive_soft.title", rusty_pipes: "f.rusty_pipes.title",
    hard_alkaline: "f.hard_alkaline.title", algae_lime: "f.algae_lime.title",
    salinity: "f.salinity.title", salty_taste: "f.salty_taste.title",
    distribution_fault: "f.distribution_fault.title", acidic_ph: "f.acidic_ph.title",
    alkaline_ph: "f.alkaline_ph.title", cloudy: "f.cloudy.title",
    slightly_cloudy: "f.slightly_cloudy.title", very_high_tds: "f.very_high_tds.title",
    high_tds: "f.high_tds.title", low_do: "f.low_do.title",
    very_low_do: "f.very_low_do.title", nothing_found: "f.nothing_found.title"
  };

  function buildMessage() {
    var problems = (R.findings || []).map(function (code) {
      return t(SEV_LABEL[code] || ("f." + code + ".title"));
    }).join(", ") || t("f.nothing_found.title");

    var notices = (R.reports || []).map(function (x) {
      return t("report." + x);
    }).join(", ") || "-";

    var doValue = (R.do === null || R.do === undefined) ? t("result.not_tested") : (R.do + " mg/L");
    var lines = [
      t("result.report_cta") + " - " + R.ward + ", " + R.zone,
      "",
      (window.AquaI18n && window.AquaI18n.lang === "ta" ? "நேரம்: " : "Time: ") + R.time,
      "pH: " + R.ph + " | Turbidity: " + R.turbidity + " NTU | TDS: " + R.tds +
        " mg/L | DO: " + doValue,
      (window.AquaI18n && window.AquaI18n.lang === "ta"
        ? "கவனித்தவை: " : "What we noticed: ") + notices,
      (window.AquaI18n && window.AquaI18n.lang === "ta"
        ? "கண்டறிதல்: " : "Diagnosis: ") + problems,
      "Status: " + R.status,
      "",
      t("result.disclaimer")
    ];
    if (R.note) lines.splice(5, 0, (window.AquaI18n && window.AquaI18n.lang === "ta"
      ? "குறிப்பு: " : "Note: ") + R.note);
    return lines.join("\n");
  }

  function refresh() {
    if (area) area.value = buildMessage();
    var email = document.getElementById("email-link");
    if (email) {
      var subject = "Water problem - " + R.ward + ", " + R.zone + " (AquaTrace #" + R.id + ")";
      email.setAttribute("href", "mailto:?subject=" + encodeURIComponent(subject) +
        "&body=" + encodeURIComponent(buildMessage()));
    }
  }

  var copyBtn = document.getElementById("copy-message");
  if (copyBtn) {
    copyBtn.addEventListener("click", function () {
      var text = buildMessage();
      var done = function () { window.aqToast(t("result.copied")); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {
          if (area) { area.focus(); area.select(); document.execCommand("copy"); done(); }
        });
      } else if (area) {
        area.focus(); area.select();
        try { document.execCommand("copy"); } catch (e) { /* ignore */ }
        done();
      }
    });
  }

  document.addEventListener("aq:lang", refresh);
  refresh();
})();
