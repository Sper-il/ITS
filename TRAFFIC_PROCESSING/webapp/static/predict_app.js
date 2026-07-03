/*
* predict_app.js. Wires Quick Predict HTML to /api/predict.
*
* Strategy: capture current values of sliders/checkboxes, POST to /api/predict
* on every change + on initial load, and update:
*   - The big "E / Kẹt xe" hero card
*   - The advice strip
*   - The confidence bar
*   - The probability bar chart (6 bars)
*   - The JSON dump
*/
const PredictApp = (() => {
  // ── DOM refs ───────────────────────────────────────────────────
  const $ = (sel) => document.querySelector(sel);
  function setText(sel, val) { const n = $(sel); if (n) n.textContent = val; }
  function setStyle(sel, prop, val) { const n = $(sel); if (n) n.style[prop] = val; }

  function getSliders() {
    return {
      length:       parseFloat(document.getElementById('slider-length')?.value || 1240),
      max_velocity: parseFloat(document.getElementById('slider-speed')?.value || 60),
      vc_ratio:     parseFloat(document.getElementById('slider-vc')?.value || 85) / 100,
      hour:         parseInt(document.getElementById('slider-hour')?.value || "18", 10),
    };
  }

  function getCheckboxes() {
    const cbs = document.querySelectorAll('input[type="checkbox"]');
    return {
      is_weekend: cbs[0]?.checked || false,
      is_rush:    cbs[1]?.checked || false,
    };
  }

  function readInputs() {
    return { ...getSliders(), ...getCheckboxes() };
  }

  function updateRangeLabels() {
    const sLength = document.getElementById('slider-length');
    const sSpeed  = document.getElementById('slider-speed');
    const sVc     = document.getElementById('slider-vc');
    const sHour   = document.getElementById('slider-hour');

    const vLength = document.getElementById('val-length');
    const vSpeed  = document.getElementById('val-speed');
    const vVc     = document.getElementById('val-vc');
    const vHour   = document.getElementById('val-hour');

    if (sLength && vLength) vLength.innerHTML = `${parseFloat(sLength.value).toLocaleString()}<small class="ml-1 opacity-60">m</small>`;
    if (sSpeed && vSpeed)   vSpeed.innerHTML  = `${sSpeed.value}<small class="ml-1 opacity-60">km/h</small>`;
    if (sVc && vVc)         vVc.textContent   = (parseFloat(sVc.value) / 100).toFixed(2);
    if (sHour && vHour)     vHour.textContent = `${String(sHour.value).padStart(2, "0")}:00`;
  }

  // ── Render response into DOM ──────────────────────────────────
  function render(r) {
    const letter = r.prediction;
    const adv = LOS_ADVICE[letter] || {};
    const color = r.color;

    // Hero big letter + name + description
    const heroLetter = $(".font-mono-data.text-\\[10rem\\]");
    if (heroLetter) {
      heroLetter.textContent = letter;
      // Replace glow colour
      heroLetter.style.textShadow = `0 0 30px ${color}99`;
      heroLetter.style.color = color;
    }
    const heroName = $(".text-display-lg.font-bold");
    if (heroName) {
      heroName.textContent = r.name;
      heroName.style.color = color;
    }
    const heroDesc = $(".text-display-lg + p");
    if (heroDesc) heroDesc.textContent = r.description;

    // Confidence
    const confText = $(".text-headline-sm.font-mono-data.font-bold.text-primary");
    if (confText) confText.textContent = `${(r.confidence * 100).toFixed(1)}%`;
    const confBar = $(".h-1\\.5.flex-1 > div, .h-1\\.5 > div");
    if (confBar) {
      confBar.style.width = (r.confidence * 100).toFixed(1) + "%";
      confBar.style.background = color;
    }

    // CRITICAL CONGESTION badge
    const badge = $(".bg-error\\/20.px-3.py-1");
    if (badge) {
      const labels = {
        A: "LƯU THÔNG TỰ DO",  B: "ỔN ĐỊNH",   C: "ĐÔNG ĐÚC",
        D: "GẦN BÃO HÒA", E: "ÙN TẮC NGHIÊM TRỌNG", F: "KẸT CỨNG",
      };
      badge.textContent = labels[letter] || letter;
      badge.style.color = color;
      badge.style.borderColor = color + "55";
      badge.style.background = color + "22";
    }

    // Border left on hero card
    const heroCard = $(".border-l-8");
    if (heroCard) {
      heroCard.style.borderLeftColor = color;
    }
    // Glow blur
    const heroGlow = $(".absolute.-right-20.-top-20");
    if (heroGlow) heroGlow.style.background = `${color}0D`;

    // Operational advice strip
    const adviceP = document.querySelector(".bg-error\\/10 p, .bg-\\[var\\(--hero-glow\\)\\] p");
    // Fallback: any p in the second card
    const allP = document.querySelectorAll("p.text-body-md");
    let adviceTarget = null;
    for (const p of allP) {
      if (p.textContent.includes("kẹt xe") || p.textContent.includes("Khuyến nghị")) {
        adviceTarget = p;
      }
    }
    // Better: find by parent section
    const adviceCard = $(".bg-error\\/10, [class*='advice']");
    // Use the operational advice block, identified by the warning_amber icon
    const warningIcon = document.querySelector(".material-symbols-outlined.text-error");
    let adviceContainer = warningIcon?.closest(".rounded-2xl");
    if (adviceContainer) {
      const adviceTitle = adviceContainer.querySelector("h4");
      const adviceText  = adviceContainer.querySelector("p");
      if (adviceTitle) {
        adviceTitle.textContent = "Khuyến nghị điều hành";
        adviceTitle.style.color = adv.color || color;
      }
      if (adviceText) {
        adviceText.textContent = r.advice;
        adviceText.style.color = (adv.color || color) + "CC";
      }
      // Tint the parent container
      adviceContainer.style.background = (adv.color || color) + "1A";
      adviceContainer.style.borderColor = (adv.color || color) + "33";
    }

    // Probability bars (6 bars + A-F labels)
    const bars = document.querySelectorAll(".chart-bar");
    if (bars.length >= 6 && r.probability) {
      r.probability.forEach((p, i) => {
        const bar = bars[i];
        if (!bar) return;
        const pct = p.percent;
        bar.style.height = Math.max(pct, 4) + "%";
        bar.style.background = p.color + (i === r.probability.findIndex(x => x.value === Math.max(...r.probability.map(y => y.value))) ? "" : "33");
        bar.style.borderTopColor = p.color + (i === r.probability.findIndex(x => x.value === Math.max(...r.probability.map(y => y.value))) ? "" : "99");
        const label = bar.querySelector("div");
        if (label) label.textContent = p.value.toFixed(2);
      });
    }

    // JSON dump
    const jsonBlock = document.querySelector("pre.font-mono-data");
    if (jsonBlock) {
      const dump = {
        request_id: "req_" + Math.random().toString(36).slice(2, 10),
        prediction: r.prediction,
        probabilities: r.probability.map(p => p.value),
        confidence_score: r.confidence,
        input: r.input,
        raw_features: r.raw_features,
      };
      jsonBlock.textContent = JSON.stringify(dump, null, 2);
    }
  }

  // ── Wire events ────────────────────────────────────────────────
  let timer;
  async function refresh() {
    try {
      const r = await API.post("/api/predict", readInputs());
      render(r);
    } catch (ex) {
      console.error("predict refresh:", ex);
    }
  }

  function wire() {
    document.querySelectorAll("input").forEach(inp => {
      inp.addEventListener("input", () => {
        updateRangeLabels();
        clearTimeout(timer);
        timer = setTimeout(refresh, 150);
      });
      inp.addEventListener("change", () => {
        updateRangeLabels();
        clearTimeout(timer);
        timer = setTimeout(refresh, 150);
      });
    });
    // Predict button click handler
    const predictBtn = document.getElementById("predict-btn");
    if (predictBtn) {
      predictBtn.addEventListener("click", () => {
        clearTimeout(timer);
        refresh();
      });
    }
    // Top nav links
    document.querySelectorAll("nav a").forEach(a => {
      const t = a.textContent.trim();
      if (t === "Tổng quan" || t === "Overview") a.href = "/overview";
      else if (t === "Dự đoán nhanh" || t === "Quick Predict") a.href = "/predict";
      else if (t === "Tìm đường" || t === "Routing") a.href = "/routing";
    });
    updateRangeLabels();
    refresh();
  }

  return { wire };
})();

    document.addEventListener("DOMContentLoaded", PredictApp.wire);




/* ── Export Model Distribution ─────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.querySelector("button:has(.material-symbols-outlined)");
  for (const el of document.querySelectorAll("button")) {
    if (el.textContent.includes("Xuất phân phối mô hình") || el.textContent.includes("Export Model Distribution")) {
      el.addEventListener("click", () => {
        const bars = document.querySelectorAll(".chart-bar");
        const headers = ["LOS", "Probability", "Percent", "Color"];
        const rows = [];
        const jsonBlock = document.querySelector("pre.font-mono-data");
        let probs = null;
        if (jsonBlock) {
          try {
            const parsed = JSON.parse(jsonBlock.textContent);
            probs = parsed.probabilities;
          } catch (_) {}
        }
        const letters = ["A", "B", "C", "D", "E", "F"];
        letters.forEach((ltr, i) => {
          const bar = bars[i];
          const pct = bar ? bar.style.height || "0%" : "0%";
          const prob = probs && probs[i] !== undefined ? probs[i] : parseFloat(pct) / 100;
          rows.push([
            ltr,
            prob.toFixed(4),
            (prob * 100).toFixed(1) + "%",
            LOS_COLORS[ltr] || "#888",
          ]);
        });
        const csv = [headers, ...rows].map(r => r.join(",")).join("\n");
        const blob = new Blob([csv], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `los_distribution_${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      });
      break;
    }
  }
});
