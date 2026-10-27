"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("predictionForm");
  const bpmInput = document.getElementById("bpmInput");
  const tempInput = document.getElementById("temperatureInput");
  const spo2Input = document.getElementById("spo2Input");
  const predictBtn = document.getElementById("predictButton");

  const resultContainer = document.getElementById("predictionResult");
  const badge = document.getElementById("predictionBadge");
  const scoreEl = document.getElementById("predictionScore");
  const thresholdEl = document.getElementById("predictionThreshold");
  const probBarFill = document.getElementById("probBarFill");
  const probBarLabel = document.getElementById("probBarLabel");
  const warningEl = document.getElementById("predictionWarning");

  // 1. Preset Buttons
  const presetBtns = document.querySelectorAll(".preset-btn");
  presetBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (bpmInput) bpmInput.value = btn.getAttribute("data-bpm");
      if (tempInput) tempInput.value = btn.getAttribute("data-temp");
      if (spo2Input) spo2Input.value = btn.getAttribute("data-spo2");
      // Trigger submission
      form.requestSubmit();
    });
  });

  // 2. Form submission
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const bpm = parseFloat(bpmInput.value);
      const temperature = parseFloat(tempInput.value);
      const spo2 = parseFloat(spo2Input.value);

      if (isNaN(bpm) || isNaN(temperature) || isNaN(spo2)) {
        alert("Please enter valid numerical readings.");
        return;
      }

      predictBtn.disabled = true;
      predictBtn.textContent = "Running Inference…";

      try {
        const res = await fetch("/api/predict", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ bpm, temperature, spo2 }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error || `HTTP ${res.status}`);
        }

        const data = await res.json();
        const pred = data.prediction;

        resultContainer.style.display = "block";

        const isRisk = pred.prediction === "SEPSIS_RISK_FLAG";
        badge.className = isRisk ? "badge-risk" : "badge-normal";
        badge.textContent = pred.prediction;

        const probPercent = (pred.sepsis_probability * 100).toFixed(2);
        scoreEl.textContent = `${probPercent}%`;
        scoreEl.style.color = isRisk ? "var(--coral-400)" : "var(--teal-400)";

        thresholdEl.textContent = (pred.threshold || 0.01).toFixed(3);

        if (probBarFill && probBarLabel) {
          // Scale visual: 0 to 5% fills 100% of bar for visual clarity
          const visualWidth = Math.min(100, (pred.sepsis_probability / 0.05) * 100);
          probBarFill.style.width = `${visualWidth}%`;
          probBarFill.style.background = isRisk ? "var(--coral-500)" : "var(--teal-500)";
          probBarLabel.textContent = `${probPercent}% (Risk threshold: 1.0%)`;
        }

        if (warningEl) {
          warningEl.textContent = pred.warning || "Experimental output. Not a medical diagnosis.";
        }
      } catch (err) {
        alert(`Prediction error: ${err.message}`);
      } finally {
        predictBtn.disabled = false;
        predictBtn.textContent = "Run Model Inference →";
      }
    });
  }

  // 3. Load metadata from /api/model-metadata
  const loadMetadata = async () => {
    try {
      const res = await fetch("/api/model-metadata");
      if (!res.ok) return;
      const meta = await res.json();

      const testMetrics = meta.test_metrics || {};
      const formatPct = (val) => (val != null ? `${(val * 100).toFixed(2)}%` : "—");

      const accEl = document.getElementById("testAccuracy");
      const precEl = document.getElementById("testPrecision");
      const recEl = document.getElementById("testRecall");
      const aucEl = document.getElementById("testAuc");
      const metaThresh = document.getElementById("metaThreshold");

      if (accEl) accEl.textContent = formatPct(testMetrics.accuracy);
      if (precEl) precEl.textContent = formatPct(testMetrics.precision);
      if (recEl) recEl.textContent = formatPct(testMetrics.recall);
      if (aucEl) aucEl.textContent = testMetrics.roc_auc ? testMetrics.roc_auc.toFixed(4) : "—";
      if (metaThresh) metaThresh.textContent = meta.selected_threshold || "0.01";
    } catch (_) {}
  };

  loadMetadata();
});
