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

  // 0. Animated EKG Canvas
  const canvas = document.getElementById("mlEkgCanvas");
  let currentBpm = 82;
  let isRiskState = false;

  if (canvas) {
    const ctx = canvas.getContext("2d");
    let width = (canvas.width = canvas.offsetWidth || 360);
    let height = (canvas.height = canvas.offsetHeight || 90);

    window.addEventListener("resize", () => {
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    });

    let x = 0;
    let points = [];

    function renderEKG() {
      ctx.fillStyle = "rgba(4, 8, 16, 0.15)";
      ctx.fillRect(0, 0, width, height);

      const speed = (currentBpm / 60) * 2.8;
      x = (x + speed) % width;

      const cycle = x % 140;
      let y = height / 2;

      if (cycle > 50 && cycle < 58) {
        y -= 6;
      } else if (cycle >= 58 && cycle < 62) {
        y += 4;
      } else if (cycle >= 62 && cycle < 68) {
        y -= 26;
      } else if (cycle >= 68 && cycle < 74) {
        y += 10;
      } else if (cycle >= 84 && cycle < 96) {
        y -= 8;
      }

      ctx.beginPath();
      ctx.strokeStyle = isRiskState ? "#EF4444" : "#0EA5E9";
      ctx.lineWidth = 2.2;
      ctx.shadowBlur = 8;
      ctx.shadowColor = ctx.strokeStyle;
      ctx.moveTo(x - speed, points[points.length - 1] || y);
      ctx.lineTo(x, y);
      ctx.stroke();

      points.push(y);
      if (points.length > width) points.shift();

      requestAnimationFrame(renderEKG);
    }

    renderEKG();

    if (bpmInput) {
      bpmInput.addEventListener("input", () => {
        const val = parseFloat(bpmInput.value);
        if (!isNaN(val) && val > 30) currentBpm = val;
      });
    }
  }

  // 1. Preset Buttons
  const presetBtns = document.querySelectorAll(".preset-btn");
  presetBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (bpmInput) {
        bpmInput.value = btn.getAttribute("data-bpm");
        currentBpm = parseFloat(bpmInput.value);
      }
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
        isRiskState = isRisk;
        currentBpm = bpm;
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
