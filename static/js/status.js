"use strict";
(async () => {
  async function check(url) {
    const response = await fetch(url, {headers: {Accept: "application/json"}});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  try { const data = await check("/api/health"); document.getElementById("statusApiTitle").textContent = "Reachable"; document.getElementById("statusApiText").textContent = `${data.service || "Flask API"} responded successfully.`; }
  catch (e) { document.getElementById("statusApiTitle").textContent = "Unavailable"; document.getElementById("statusApiText").textContent = e.message; }
  try { const data = await check("/api/model-metadata"); document.getElementById("statusMetadataTitle").textContent = "Available"; document.getElementById("statusMetadataText").textContent = `Experiment: ${data.experiment || "configured model"}; threshold: ${data.selected_threshold ?? "not supplied"}.`; }
  catch (e) { document.getElementById("statusMetadataTitle").textContent = "Unavailable"; document.getElementById("statusMetadataText").textContent = e.message; }
  try { const data = await check("/api/readings"); document.getElementById("statusReadingsTitle").textContent = "Reachable"; document.getElementById("statusReadingsText").textContent = `${data.count} recent record(s) returned by the API.`; }
  catch (e) { document.getElementById("statusReadingsTitle").textContent = "Unavailable"; document.getElementById("statusReadingsText").textContent = e.message; }
})();
