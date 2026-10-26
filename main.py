import math

from flask import Flask, render_template, request, jsonify
from explanation_service import explain_reading
from database import (
    initialize_database,
    get_latest_reading,
    get_recent_readings,
    insert_reading,
)
from prediction_service import predict_reading

app = Flask(__name__)
initialize_database()

@app.route("/")
def home():
    reading = get_latest_reading()
    readings = get_recent_readings()

    return render_template(
        "dashboard.html",
        reading=reading,
        readings=readings,
    )


@app.route("/api/readings", methods=["POST"])
def create_reading():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400

    required_fields = ("bpm", "temperature", "spo2")

    if not all(field in data for field in required_fields):
        return jsonify({
            "error": "Required fields: bpm, temperature, spo2"
        }), 400

    try:
        bpm = float(data["bpm"])
        temperature = float(data["temperature"])
        spo2 = float(data["spo2"])
    except (TypeError, ValueError):
        return jsonify({"error": "All readings must be numbers"}), 400

    if not all(math.isfinite(v) for v in (bpm, temperature, spo2)):
        return jsonify({"error": "Readings must be finite numbers"}), 400

    if not (0 < bpm <= 300):
        return jsonify({"error": "Invalid bpm value"}), 400

    if not (20 <= temperature <= 45):
        return jsonify({"error": "Invalid temperature value"}), 400

    if not (0 <= spo2 <= 100):
        return jsonify({"error": "Invalid spo2 value"}), 400

    try:
        prediction = predict_reading(bpm, temperature, spo2)
    except Exception:
        app.logger.exception("Prediction failed for incoming reading")
        return jsonify({
            "error": "Prediction service unavailable; reading was not stored"
        }), 503

    reading_id = insert_reading(
        bpm,
        temperature,
        spo2,
        prediction=prediction["prediction"],
        sepsis_probability=prediction["sepsis_probability"],
        prediction_threshold=prediction["threshold"],
    )

    return jsonify({
        "message": "Reading stored successfully",
        "id": reading_id,
        "prediction": prediction,
    }), 201


@app.route("/api/readings", methods=["GET"])
def list_readings():
    readings = get_recent_readings()

    return jsonify({
        "count": len(readings),
        "readings": readings
    }), 200


@app.route("/api/readings/<int:reading_id>/explanation", methods=["GET"])
def get_reading_explanation(reading_id):
    reading = None

    for item in get_recent_readings(limit=1000):
        if item["id"] == reading_id:
            reading = item
            break

    if reading is None:
        return jsonify({"error": "Reading not found"}), 404

    try:
        explanation = explain_reading(
            bpm=reading["bpm"],
            temperature=reading["temperature"],
            spo2=reading["spo2"],
        )
    except Exception as exc:
        app.logger.exception("LIME explanation generation failed")
        return jsonify({
            "error": "Could not generate explanation",
            "details": str(exc),
            "exception_type": type(exc).__name__,
        }), 500

    explanation["reading_id"] = reading_id
    explanation["timestamp"] = reading["timestamp"]

    return jsonify(explanation), 200


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)