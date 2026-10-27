"use strict";

(() => {
  const ids = ["tp", "tn", "fp", "fn"];
  const els = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
  
  const pct = value => Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "N/A";
  const ratio = (a, b) => b === 0 ? NaN : a / b;

  function update() {
    const count = {};
    for (const id of ids) {
      const val = Number(els[id]?.value);
      count[id] = Number.isSafeInteger(val) && val >= 0 ? val : 0;
    }

    const { tp, tn, fp, fn } = count;
    const total = tp + tn + fp + fn;

    const precision = ratio(tp, tp + fp);
    const recall = ratio(tp, tp + fn);
    const specificity = ratio(tn, tn + fp);
    const accuracy = ratio(tp + tn, total);
    const f1 = (Number.isFinite(precision) && Number.isFinite(recall) && (precision + recall !== 0))
      ? (2 * precision * recall) / (precision + recall)
      : NaN;

    const values = {
      matrixTP: tp,
      matrixTN: tn,
      matrixFP: fp,
      matrixFN: fn,
      metricAccuracy: pct(accuracy),
      metricPrecision: pct(precision),
      metricRecall: pct(recall),
      metricSpecificity: pct(specificity),
      metricF1: pct(f1),
      metricTotal: total.toLocaleString(),
    };

    Object.entries(values).forEach(([id, val]) => {
      const el = document.getElementById(id);
      if (el) el.textContent = String(val);
    });
  }

  ids.forEach(id => els[id]?.addEventListener("input", update));

  // Reset buttons
  document.getElementById("useModelCounts")?.addEventListener("click", () => {
    els.tp.value = "26";
    els.tn.value = "1004";
    els.fp.value = "677";
    els.fn.value = "21";
    update();
  });

  document.getElementById("setBalancedCounts")?.addEventListener("click", () => {
    els.tp.value = "85";
    els.tn.value = "90";
    els.fp.value = "10";
    els.fn.value = "15";
    update();
  });

  // Threshold simulator logic
  const slider = document.getElementById("thresholdSlider");
  const threshVal = document.getElementById("thresholdValue");
  const simRecall = document.getElementById("simRecall");
  const simPrecision = document.getElementById("simPrecision");
  const simFP = document.getElementById("simFP");

  if (slider && threshVal) {
    slider.addEventListener("input", (e) => {
      const t = parseFloat(e.target.value);
      threshVal.textContent = t.toFixed(3);

      // Synthetic dynamic curves reflecting real imbalanced trade-offs
      // At t=0.01: recall ~ 55.3%, FP ~ 677, precision ~ 3.7%
      // As t increases: recall drops, FP drops rapidly, precision increases slightly
      const normalizedFactor = t / 0.01;
      const rec = Math.max(5, Math.min(95, 55.3 / Math.pow(normalizedFactor, 0.45)));
      const fp = Math.max(12, Math.round(677 / Math.pow(normalizedFactor, 0.8)));
      const tp = Math.round(47 * (rec / 100));
      const prec = (tp / (tp + fp)) * 100;

      if (simRecall) simRecall.textContent = `${rec.toFixed(1)}%`;
      if (simPrecision) simPrecision.textContent = `${prec.toFixed(1)}%`;
      if (simFP) simFP.textContent = String(fp);
    });
  }

  update();
})();
