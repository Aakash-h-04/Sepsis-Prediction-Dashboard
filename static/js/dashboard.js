
"use strict";

const API_URL = "/api/readings";
const REFRESH_INTERVAL = 1000;

let vitalsChart = null;

const elements = {
    apiDot: document.getElementById("apiDot"),
    apiStatus: document.getElementById("apiStatus"),
    dataDot: document.getElementById("dataDot"),
    dataStatus: document.getElementById("dataStatus"),
    dataDescription: document.getElementById("dataDescription"),
    recordCount: document.getElementById("recordCount"),
    lastUpdated: document.getElementById("lastUpdated"),
    bpmValue: document.getElementById("bpmValue"),
    temperatureValue: document.getElementById("temperatureValue"),
    spo2Value: document.getElementById("spo2Value"),
    tableBody: document.getElementById("readingsTableBody"),
    chartEmpty: document.getElementById("chartEmpty"),
    chartRecordInfo: document.getElementById("chartRecordInfo")
};

function numericValue(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }

    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

function formatNumber(value, digits = 1) {
    const number = numericValue(value);
    return number === null ? "--" : number.toFixed(digits);
}

function timestampDate(value) {
    if (!value) return null;

    // SQLite CURRENT_TIMESTAMP is UTC without a timezone suffix.
    const text = String(value);

    const normalized =
        /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(text)
            ? text.replace(" ", "T") + "Z"
            : text;

    const date = new Date(normalized);

    return Number.isNaN(date.getTime()) ? null : date;
}

function formatTimestamp(value) {
    const date = timestampDate(value);

    return date
        ? date.toLocaleString([], {
            year: "numeric",
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        })
        : (value || "Unknown");
}

function setDot(element, state) {
    if (!element) return;

    element.classList.remove("online", "warning", "offline");

    if (state) {
        element.classList.add(state);
    }
}

function setMetric(element, value, unit, digits = 1) {
    if (!element) return;

    const formatted = formatNumber(value, digits);

    element.replaceChildren();
    element.append(document.createTextNode(formatted + " "));

    const unitElement = document.createElement("span");
    unitElement.textContent = unit;

    element.append(unitElement);
}

function renderTable(readings) {
    if (!elements.tableBody) return;

    elements.tableBody.replaceChildren();

    if (readings.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 5;
        cell.className = "empty-table";
        cell.textContent = "No readings recorded yet.";

        row.append(cell);
        elements.tableBody.append(row);
        return;
    }

    readings.forEach(item => {
        const row = document.createElement("tr");

        const values = [
            { text: `#${item.id}`, className: "record-id" },
            { text: formatTimestamp(item.timestamp) },
            { text: formatNumber(item.bpm, 1), unit: "BPM" },
            { text: formatNumber(item.temperature, 2), unit: "°C" },
            { text: formatNumber(item.spo2, 1), unit: "%" }
        ];

        values.forEach(value => {
            const cell = document.createElement("td");

            if (value.className) {
                const span = document.createElement("span");

                span.className = value.className;
                span.textContent = value.text;

                cell.append(span);
            } else if (value.unit) {
                cell.append(document.createTextNode(value.text + " "));

                const unit = document.createElement("span");

                unit.className = "table-unit";
                unit.textContent = value.unit;

                cell.append(unit);
            } else {
                cell.textContent = value.text;
            }

            row.append(cell);
        });

        elements.tableBody.append(row);
    });
}

function chartOptions() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,

        interaction: {
            mode: "index",
            intersect: false
        },

        plugins: {
            legend: {
                display: false
            },

            tooltip: {
                backgroundColor: "#101827",
                titleColor: "#F1F5F9",
                bodyColor: "#CBD5E1",
                borderColor: "#293548",
                borderWidth: 1,
                padding: 12,

                callbacks: {
                    label(context) {
                        const units = {
                            bpm: " BPM",
                            temperature: " °C",
                            spo2: "%"
                        };

                        const value = context.parsed.y;

                        return `${context.dataset.label}: ${
                            value === null ? "--" : value
                        }${units[context.dataset.yAxisID] || ""}`;
                    }
                }
            }
        },

        scales: {
            x: {
                grid: {
                    color: "#293548",
                    drawTicks: false
                },

                border: {
                    display: false
                },

                ticks: {
                    color: "#94A3B8",
                    maxTicksLimit: 7,
                    maxRotation: 0,
                    font: {
                        size: 10
                    }
                }
            },

            bpm: {
                type: "linear",
                position: "left",

                title: {
                    display: true,
                    text: "BPM",
                    color: "#FB7185",
                    font: {
                        size: 10
                    }
                },

                grid: {
                    color: "#293548"
                },

                border: {
                    display: false
                },

                ticks: {
                    color: "#94A3B8",
                    font: {
                        size: 10
                    }
                }
            },

            temperature: {
                type: "linear",
                position: "right",

                title: {
                    display: true,
                    text: "°C",
                    color: "#FBBF24",
                    font: {
                        size: 10
                    }
                },

                grid: {
                    drawOnChartArea: false
                },

                border: {
                    display: false
                },

                ticks: {
                    color: "#94A3B8",
                    font: {
                        size: 10
                    }
                }
            },

            spo2: {
                type: "linear",
                display: false,
                min: 0,
                max: 100
            }
        }
    };
}

function updateChart(readings) {
    const canvas = document.getElementById("vitalsChart");

    if (!canvas) {
        console.error("Chart error: #vitalsChart canvas was not found.");
        return;
    }

    if (!elements.chartEmpty || !elements.chartRecordInfo) {
        console.error("Chart error: chart status elements are missing.");
        return;
    }

    if (!window.Chart) {
        elements.chartEmpty.textContent =
            "Chart library unavailable. Check your internet connection.";

        elements.chartEmpty.style.display = "grid";

        console.error("Chart error: Chart.js is not loaded.");
        return;
    }

    const ordered = [...readings].reverse();

    const labels = ordered.map(item => {
        const date = timestampDate(item.timestamp);

        return date
            ? date.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit"
            })
            : String(item.timestamp || "");
    });

    const datasets = [
        {
            label: "Heart rate",
            yAxisID: "bpm",
            data: ordered.map(item => numericValue(item.bpm)),
            borderColor: "#FB7185",
            backgroundColor: "#FB718514",
            pointBackgroundColor: "#FB7185",
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 2,
            tension: 0.25,
            spanGaps: false
        },
        {
            label: "Temperature",
            yAxisID: "temperature",
            data: ordered.map(item => numericValue(item.temperature)),
            borderColor: "#FBBF24",
            backgroundColor: "#FBBF2414",
            pointBackgroundColor: "#FBBF24",
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 2,
            tension: 0.25,
            spanGaps: false
        },
        {
            label: "SpO₂",
            yAxisID: "spo2",
            data: ordered.map(item => numericValue(item.spo2)),
            borderColor: "#2DD4BF",
            backgroundColor: "#2DD4BF14",
            pointBackgroundColor: "#2DD4BF",
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 2,
            tension: 0.25,
            spanGaps: false
        }
    ];

    elements.chartEmpty.textContent = "Waiting for recorded measurements.";

    elements.chartEmpty.style.display =
        ordered.length > 0 ? "none" : "grid";

    elements.chartRecordInfo.textContent =
        `${ordered.length} recorded observation${
            ordered.length === 1 ? "" : "s"
        }`;

    try {
        // Diagnostic output: inspect this in Chrome DevTools.
        console.log("Chart debug:", {
            readingCount: readings.length,
            chartLibrary: typeof Chart,
            chartCanvas: canvas,
            existingChart: Chart.getChart(canvas)
        });

        if (!vitalsChart) {
            vitalsChart = new Chart(canvas, {
                type: "line",
                data: {
                    labels,
                    datasets
                },
                options: chartOptions()
            });

            console.log("Chart created successfully:", vitalsChart);
        } else {
            vitalsChart.data.labels = labels;

            vitalsChart.data.datasets.forEach((dataset, index) => {
                dataset.data = datasets[index].data;
            });

            vitalsChart.update("none");
        }
    } catch (error) {
        elements.chartEmpty.textContent =
            "The chart could not be rendered. Check the browser console.";

        elements.chartEmpty.style.display = "grid";

        console.error("Chart initialization failed:", error);
    }
}

function updateStatus(readings) {
    if (readings.length === 0) {
        setDot(elements.dataDot, "warning");

        if (elements.dataStatus) {
            elements.dataStatus.textContent = "No readings available";
        }

        if (elements.dataDescription) {
            elements.dataDescription.textContent =
                "The API is reachable, but no records were returned.";
        }

        if (elements.lastUpdated) {
            elements.lastUpdated.textContent = "No readings available";
        }

        return;
    }

    const latest = readings[0];
    const date = timestampDate(latest.timestamp);

    if (elements.lastUpdated) {
        elements.lastUpdated.textContent =
            formatTimestamp(latest.timestamp);
    }

    if (!date) {
        setDot(elements.dataDot, "warning");

        if (elements.dataStatus) {
            elements.dataStatus.textContent = "Timestamp unavailable";
        }

        if (elements.dataDescription) {
            elements.dataDescription.textContent =
                "Readings exist, but data freshness could not be determined.";
        }

        return;
    }

    const ageSeconds = Math.max(
        0,
        (Date.now() - date.getTime()) / 1000
    );

    if (ageSeconds > 60) {
        setDot(elements.dataDot, "warning");

        if (elements.dataStatus) {
            elements.dataStatus.textContent =
                "Latest reading is not recent";
        }

        if (elements.dataDescription) {
            elements.dataDescription.textContent =
                "The newest stored record is more than 60 seconds old.";
        }
    } else {
        setDot(elements.dataDot, "online");

        if (elements.dataStatus) {
            elements.dataStatus.textContent = "Recent reading available";
        }

        if (elements.dataDescription) {
            elements.dataDescription.textContent =
                "The newest stored record is less than 60 seconds old.";
        }
    }
}

async function refreshDashboard() {
    try {
        const response = await fetch(API_URL, {
            headers: {
                "Accept": "application/json"
            },
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error(`API returned HTTP ${response.status}`);
        }

        const payload = await response.json();

        const readings = Array.isArray(payload.readings)
            ? payload.readings
            : Array.isArray(payload.recent_readings)
                ? payload.recent_readings
                : [];

        setDot(elements.apiDot, "online");

        if (elements.apiStatus) {
            elements.apiStatus.textContent = "Backend reachable";
        }

        if (elements.recordCount) {
            elements.recordCount.textContent =
                payload.count ?? readings.length;
        }

        if (readings.length > 0) {
            const latest = readings[0];

            setMetric(elements.bpmValue, latest.bpm, "BPM");
            setMetric(
                elements.temperatureValue,
                latest.temperature,
                "°C",
                2
            );
            setMetric(elements.spo2Value, latest.spo2, "%");
        }

        renderTable(readings);

        // Diagnostic output to confirm the API data reaches the chart.
        console.log("Dashboard data received:", {
            count: payload.count,
            readingCount: readings.length,
            firstReading: readings[0]
        });

        updateChart(readings);
        updateStatus(readings);

    } catch (error) {
        setDot(elements.apiDot, "offline");
        setDot(elements.dataDot, "offline");

        if (elements.apiStatus) {
            elements.apiStatus.textContent = "Backend unavailable";
        }

        if (elements.dataStatus) {
            elements.dataStatus.textContent =
                "Unable to refresh readings";
        }

        if (elements.dataDescription) {
            elements.dataDescription.textContent =
                "Check that Flask is running and the readings API is available.";
        }

        console.error("Dashboard refresh failed:", error);
    }
}

refreshDashboard();
setInterval(refreshDashboard, REFRESH_INTERVAL);


/* --------------------------------------------------
   LIME explainability panel
-------------------------------------------------- */

const explanationButton = document.getElementById("explainReadingButton");
const explanationIdInput = document.getElementById("explanationReadingId");
const explanationStatus = document.getElementById("explanationStatus");
const explanationResults = document.getElementById("explanationResults");

if (explanationButton) {
    explanationButton.addEventListener("click", async () => {
        const readingId = Number(explanationIdInput.value);

        if (!Number.isInteger(readingId) || readingId < 1) {
            explanationStatus.textContent = "Enter a valid reading ID.";
            explanationResults.hidden = true;
            return;
        }

        explanationButton.disabled = true;
        explanationButton.textContent = "Generating explanation...";
        explanationStatus.textContent = "Requesting LIME explanation...";
        explanationResults.hidden = true;

        try {
            const response = await fetch(
                `/api/readings/${readingId}/explanation`
            );

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || "Could not explain this reading.");
            }

            document.getElementById("explanationPrediction").textContent =
                result.prediction.replaceAll("_", " ");

            document.getElementById("explanationProbability").textContent =
                `${(result.sepsis_probability * 100).toFixed(2)}%`;

            document.getElementById("explanationThreshold").textContent =
                `${(result.threshold * 100).toFixed(2)}%`;

            const featureContainer =
                document.getElementById("explanationFeatures");

            featureContainer.replaceChildren();

            for (const item of result.explanation) {
                const row = document.createElement("div");
                row.className = "explanation-feature";

                const label = document.createElement("span");
                label.className = "explanation-feature-label";
                label.textContent = item.feature_rule;

                const effect = document.createElement("span");
                effect.className = item.weight >= 0
                    ? "explanation-effect positive"
                    : "explanation-effect negative";
                effect.textContent =
                    `${item.effect} (${item.weight.toFixed(4)})`;

                row.append(label, effect);
                featureContainer.appendChild(row);
            }

            document.getElementById("explanationWarning").textContent =
                result.warning;

            explanationStatus.textContent =
                `Explanation generated for reading #${result.reading_id}.`;

            explanationResults.hidden = false;

        } catch (error) {
            explanationStatus.textContent = error.message;
        } finally {
            explanationButton.disabled = false;
            explanationButton.textContent = "Explain reading";
        }
    });
}
