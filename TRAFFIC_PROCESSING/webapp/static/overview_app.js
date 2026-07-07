/*
* overview_app.js. Wires the static overview HTML to /api/*.
* Uses explicit DOM IDs for reliable data binding.
*/
(async function () {
  // ── Helpers ───────────────────────────────────────────────────────
  function q1(sel) { return document.querySelector(sel); }
  function qA(sel) { return Array.from(document.querySelectorAll(sel)); }

  function setText(sel, val) {
    const node = q1(sel);
    if (node) node.textContent = val;
  }

  try {
    // ── Live update: sidebar accuracy ──────────────────────────────
    const sumRes = await API.get("/api/overview/summary");
    const m = sumRes.validation || {};
    const accuracyPill = q1("#sidebar-accuracy");
    if (accuracyPill && m.val_accuracy != null) {
      accuracyPill.textContent = "Độ chính xác " + (m.val_accuracy * 100).toFixed(1).replace(".", ",") + "%";
    }

    // ── KPI tiles ──────────────────────────────────────────────────
    setText("#kpi-samples", sumRes.samples.toLocaleString());
    setText("#kpi-mean-conf", fmtPercent(sumRes.mean_conf, 1));

    const domLos = q1("#kpi-dominant-los");
    if (domLos) {
      domLos.textContent = "LOS " + sumRes.dominant_los;
      domLos.style.color = sumRes.dominant_color;
    }
    setText("#kpi-dominant-name", sumRes.dominant_name);
    setText("#kpi-conf-ratio", fmtPercent(sumRes.mean_conf, 2) + "/1.00");

    const confBar = q1("#kpi-conf-bar");
    if (confBar) confBar.style.width = (sumRes.mean_conf * 100).toFixed(1) + "%";
    setText("#kpi-conf-pct", Math.round(sumRes.mean_conf * 100) + "%");

    // ── Donut center ───────────────────────────────────────────────
    setText("#donut-center-count", sumRes.samples.toLocaleString());

    // ── Donut chart (replace stroke-dasharray + dashoffset) ────────
    const distRes = await API.get("/api/overview/distribution");
    let offset = 100;
    distRes.rows.forEach((row) => {
      const node = q1(`#donut-${row.letter}`);
      if (node) {
        node.setAttribute("stroke-dasharray", `${row.percent} ${100 - row.percent}`);
        node.setAttribute("stroke-dashoffset", String(offset));
        offset -= row.percent;
      }
    });

    // Side percentages "A: 12%"
    distRes.rows.forEach(row => {
      const node = q1(`.los-pct-${row.letter}`);
      if (node) node.textContent = `${row.letter}: ${row.percent.toFixed(0)}%`;
    });

    // ── LOS legend counts ────────────────────────────────────────────
    const legendItems = qA(".p-panel-padding.space-y-3 .flex.items-center.justify-between.text-body-sm");
    legendItems.forEach((row) => {
      const letter = row.querySelector(".font-mono-data.font-bold.w-4")?.textContent.trim();
      if (!letter) return;
      const r = distRes.rows.find(r => r.letter === letter);
      if (!r) return;
      const counter = row.querySelector(".font-mono-data.text-on-surface-variant");
      if (counter) counter.textContent = r.count.toLocaleString() + " pts";
    });

    // ── F1 bars ────────────────────────────────────────────────────
    const f1Res = await API.get("/api/overview/f1");
    const f1Rows = qA(".glass-panel .space-y-5 > .space-y-1");
    f1Rows.forEach((rowNode, idx) => {
      const r = f1Res.rows[idx];
      if (!r) return;
      const headerSpans = rowNode.querySelectorAll(".flex.justify-between span");
      if (headerSpans[1]) headerSpans[1].textContent = Math.round(r.f1 * 100) + "%";
      const bar = rowNode.querySelector(".los-bar > div");
      if (bar) {
        bar.style.width = (r.f1 * 100).toFixed(1) + "%";
        bar.style.background = r.color;
      }
    });

    // ── Confidence histogram ──────────────────────────────────────
    const conf = await API.get("/api/overview/confidence");
    const hist = q1("#confidence-histogram");
    if (hist) {
      hist.innerHTML = "";
      const max = Math.max(...conf.counts, 1);
      conf.counts.forEach((c, i) => {
        const bar = document.createElement("div");
        bar.className = "histogram-bar bg-primary/40 flex-1 rounded-t hover:bg-primary transition-colors";
        bar.style.height = (c / max * 100) + "%";
        bar.title = `${conf.bins[i].toFixed(2)} – ${conf.bins[i+1].toFixed(2)}: ${c}`;
        hist.appendChild(bar);
      });
    }
  } catch (ex) {
    console.error("overview_app.js:", ex);
  }

  // ── Top nav links (fallback for any remaining # hrefs) ──────────
  qA("nav a").forEach(a => {
    const t = a.textContent.trim();
    if (t === "Tổng quan" || t === "Overview") a.href = "/overview";
    else if (t === "Dự đoán nhanh" || t === "Quick Predict") a.href = "/predict";
    else if (t === "Tìm đường" || t === "Routing") a.href = "/routing";
  });
})();
