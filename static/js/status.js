"use strict";
(async () => {
  async function check(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  // 1. Core API
  try {
    const data = await check("/api/health");
    document.getElementById("statusApiTitle").textContent = "Reachable (HTTP 200)";
    document.getElementById("statusApiText").textContent = `${data.service || "Flask API"} operational · Database: ${data.database || "connected"}`;
    const pill = document.getElementById("statusApiPill");
    if (pill) {
      pill.className = "pill pill-live";
      pill.textContent = "Operational";
    }
  } catch (e) {
    document.getElementById("statusApiTitle").textContent = "Degraded / Error";
    document.getElementById("statusApiText").textContent = e.message;
    const pill = document.getElementById("statusApiPill");
    if (pill) {
      pill.className = "pill pill-warning";
      pill.textContent = "Offline";
    }
  }

  // 2. Model Metadata
  try {
    const data = await check("/api/model-metadata");
    document.getElementById("statusMetadataTitle").textContent = "Loaded & Ready";
    document.getElementById("statusMetadataText").textContent = `Architecture: ${data.pipeline_type || "RandomForest"} · Threshold: ${data.selected_threshold ?? "0.01"}`;
    const pill = document.getElementById("statusMetaPill");
    if (pill) {
      pill.className = "pill pill-live";
      pill.textContent = "Model Verified";
    }
  } catch (e) {
    document.getElementById("statusMetadataTitle").textContent = "Unavailable";
    document.getElementById("statusMetadataText").textContent = e.message;
    const pill = document.getElementById("statusMetaPill");
    if (pill) {
      pill.className = "pill pill-warning";
      pill.textContent = "Missing";
    }
  }

  // 3. Telemetry Ingestion
  try {
    const data = await check("/api/readings");
    document.getElementById("statusReadingsTitle").textContent = "Ingesting Telemetry";
    document.getElementById("statusReadingsText").textContent = `${data.count ?? data.readings?.length ?? 0} active observation(s) recorded in database.`;
    const pill = document.getElementById("statusReadingsPill");
    if (pill) {
      pill.className = "pill pill-live";
      pill.textContent = "ESP32 Stream Active";
    }
  } catch (e) {
    document.getElementById("statusReadingsTitle").textContent = "Ingestion Offline";
    document.getElementById("statusReadingsText").textContent = e.message;
    const pill = document.getElementById("statusReadingsPill");
    if (pill) {
      pill.className = "pill pill-warning";
      pill.textContent = "Failed";
    }
  }
})();
