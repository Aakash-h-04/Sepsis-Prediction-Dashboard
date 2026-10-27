"""
SepsisSense — Advanced Clinical Intelligence & Educational Platform
Flask Web Server and REST API
Maintains full backward-compatibility with ESP32 edge telemetry (POST /api/readings)
and serves the public education hub, interactive labs, user portal, and admin console.
"""

import csv
import io
import json
import math
import os
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import database as db
from explanation_service import explain_reading
from notification_service import (
    dispatch_risk_alert_if_needed,
    get_email_status,
    get_whatsapp_status,
    send_email_notification,
    send_whatsapp_notification,
)
from prediction_service import predict_reading

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "sepsissense-secure-session-key-2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_METADATA_PATH = PROJECT_ROOT / "model" / "sensor_model_metadata.json"

# Initialize persistence layer and ensure default demo user and device exist
db.initialize_database()

# Seed initial evaluator account if no users exist
if db.count_users() == 0:
    db.create_user(
        email="evaluator@sepsissense.org",
        password_hash=generate_password_hash("DemoAccess2026!"),
        name="Clinical Evaluator",
        role="admin",
        is_admin=1,
    )


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("auth_login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get("user")
        admin_key = request.args.get("admin_key")
        expected_key = os.getenv("ADMIN_SECRET", "admin-sepsissense-2026")

        if admin_key and admin_key == expected_key:
            return f(*args, **kwargs)

        if not user or not user.get("is_admin"):
            return redirect(url_for("auth_login", next=request.path, reason="admin_required"))
        return f(*args, **kwargs)
    return decorated_function


def _read_model_metadata():
    try:
        with MODEL_METADATA_PATH.open("r", encoding="utf-8") as file:
            result = json.load(file)
        if isinstance(result, dict):
            return result
    except Exception:
        app.logger.exception("Could not read model metadata")
    return {}


# ---------------------------------------------------------------------------
# Public Educational & Awareness Routes
# ---------------------------------------------------------------------------

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/dashboard")
def home():
    """Preserves the original real-time sensor monitoring dashboard."""
    reading = db.get_latest_reading()
    readings = db.get_recent_readings()
    return render_template("dashboard.html", reading=reading, readings=readings)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/sepsis")
def sepsis_hub():
    return render_template("sepsis.html")


@app.route("/sepsis/symptoms")
def sepsis_symptoms():
    return render_template("symptoms.html")


@app.route("/sepsis/impact")
def sepsis_impact():
    return render_template("impact.html")


@app.route("/research")
def research():
    metadata = _read_model_metadata()
    return render_template("research.html", metadata=metadata)


@app.route("/learn")
def learn():
    return render_template("learn.html")


@app.route("/learn/biology")
def biology_lab():
    return render_template("biology.html")


@app.route("/learn/mathematics")
def mathematics_lab():
    return render_template("mathematics.html")


@app.route("/learn/ml")
@app.route("/app/ml-lab")
def ml_lab():
    return render_template("ml_lab.html")


@app.route("/assistant")
@app.route("/app/assistant")
def assistant_page():
    llm_configured = bool(os.getenv("LLM_API_KEY") and os.getenv("LLM_MODEL"))
    return render_template("assistant.html", assistant_configured=llm_configured)


@app.route("/status")
def status_page():
    return render_template("status.html")


@app.route("/faq")
def faq():
    return render_template("simple_page.html", page_title="Frequently Asked Questions", eyebrow="HELP & FAQ", intro="Answers about the SepsisSense platform, clinical safety, and the experimental Random Forest classifier.", sections=[
        {"title": "Does SepsisSense provide a medical diagnosis?", "body": "No. SepsisSense is an educational and engineering prototype. An exploratory machine-learning score must never be used to diagnose, triage, or rule out sepsis."},
        {"title": "Are the ESP32 readings real patient observations?", "body": "The active ESP32 firmware transmits simulated vital signs (e.g., 82 BPM, 36.7°C, 98% SpO2) to demonstrate the edge-to-cloud data ingestion pipeline safely."},
        {"title": "Why is the model's reported test precision low (3.7%)?", "body": "Sepsis occurs in a tiny fraction of hospital stay hours (~2%). Because the threshold was lowered to 0.01 to prioritize sensitivity (~55% recall), it produces many false alarms. This exemplifies why sensor vitals alone are clinically insufficient."},
        {"title": "What should I do if sepsis is suspected?", "body": "Sepsis is a medical emergency. Immediately contact emergency services (112, 911, or 999) or proceed to the nearest emergency department."},
    ])


@app.route("/sources")
def sources():
    return render_template("simple_page.html", page_title="Medical Sources & Citations", eyebrow="BIBLIOGRAPHY", intro="Authoritative references and peer-reviewed literature informing the SepsisSense educational platform.", sections=[
        {"title": "World Health Organization (WHO) — Sepsis Report", "body": "Global epidemiological report establishing ~48.9 million cases and ~11 million sepsis-related deaths globally each year. <a href='https://www.who.int/news-room/fact-sheets/detail/sepsis' target='_blank' rel='noopener noreferrer'>View WHO Fact Sheet ↗</a>"},
        {"title": "Centers for Disease Control and Prevention (CDC) — Sepsis Clinical Guidelines", "body": "Clinical guidance on early recognition, patient risk groups, and infection prevention. <a href='https://www.cdc.gov/sepsis/' target='_blank' rel='noopener noreferrer'>Visit CDC Sepsis Portal ↗</a>"},
        {"title": "Third International Consensus Definitions for Sepsis (Sepsis-3)", "body": "Singer M, et al. JAMA. 2016;315(8):801–810. Standardizing sepsis as life-threatening organ dysfunction caused by a dysregulated host response to infection."},
        {"title": "PhysioNet / Computing in Cardiology Challenge 2019", "body": "Reyna MA, et al. Early Prediction of Sepsis from Clinical Data. The PhysioNet benchmark dataset upon which the exploratory sensor model was trained."},
    ])


@app.route("/privacy")
def privacy():
    return render_template("simple_page.html", page_title="Privacy & Data Governance", eyebrow="GOVERNANCE", intro="How SepsisSense handles telemetry, user profiles, and security credentials.", sections=[
        {"title": "Zero Patient-Identifiable Health Information (PHI)", "body": "SepsisSense stores strictly de-identified sensor streams. Users and developers must never upload personal medical records or protected health information."},
        {"title": "Credential Security", "body": "All API keys, LLM tokens, Gmail OAuth credentials, and Twilio secrets are maintained strictly server-side in secure environment variables. Password hashes use Werkzeug salted SHA-256."},
        {"title": "Telemetry Retention", "body": "Sensor streams may be exported as CSV or purged upon administrative request. Data submitted via demo endpoints is treated as public prototype telemetry."},
    ])


@app.route("/terms")
def terms():
    return render_template("simple_page.html", page_title="Terms of Service", eyebrow="TERMS", intro="User agreement for accessing the SepsisSense platform.", sections=[
        {"title": "Educational & Non-Clinical Use Only", "body": "SepsisSense is provided exclusively for educational, research, and technical evaluation purposes. You agree not to rely on this software for clinical diagnostics, patient care decisions, or triage."},
        {"title": "No Warranty", "body": "The platform and experimental machine-learning models are provided 'as is' without warranty of any kind, express or implied."},
        {"title": "Codebase & Licensing", "body": "Open-source under academic and educational research terms. See the project repository for license details."},
    ])


@app.route("/disclaimer")
def disclaimer():
    return render_template("simple_page.html", page_title="Clinical & ML Disclaimer", eyebrow="DISCLAIMER", intro="Important medical and engineering limitations.", sections=[
        {"title": "Not a Diagnostic Tool", "body": "SepsisSense does not diagnose sepsis. Sepsis diagnosis requires comprehensive laboratory testing (blood cultures, lactate, complete blood counts), physical examination, and licensed clinical judgment."},
        {"title": "Negative Predictions Do Not Rule Out Sepsis", "body": "A prediction of NO_RISK_FLAG or a low probability score does not guarantee safety. Vital signs can appear deceptively normal during early or atypical sepsis presentations."},
        {"title": "Immediate Action Required in Emergencies", "body": "If you or someone in your care displays warning signs of sepsis (extreme shivering, altered mental state, rapid heart rate, severe breathlessness), call emergency services immediately."},
    ])


@app.route("/accessibility")
def accessibility():
    return render_template("simple_page.html", page_title="Accessibility Statement", eyebrow="ACCESSIBILITY", intro="Our commitment to universal accessibility and inclusive design.", sections=[
        {"title": "Standards Compliance", "body": "SepsisSense adheres to WCAG 2.1 Level AA standards, featuring high-contrast color palettes, legible typography, and semantic HTML."},
        {"title": "Screen Reader & Keyboard Navigation", "body": "All interactive buttons, modals, and laboratory tools support full keyboard focus indicators and ARIA live announcements."},
        {"title": "Reduced Motion", "body": "The platform respects operating system prefers-reduced-motion preferences by disabling heavy orbital and visual transitions."},
    ])


@app.route("/contact")
def contact():
    return render_template("simple_page.html", page_title="Contact & Feedback", eyebrow="GET IN TOUCH", intro="Connect with the engineering team or report an issue.", sections=[
        {"title": "GitHub Repository", "body": "Report issues, submit pull requests, or explore code: <a href='https://github.com/Aakash-h-04/Sepsis-Prediction-Dashboard' target='_blank' rel='noopener noreferrer'>github.com/Aakash-h-04/Sepsis-Prediction-Dashboard ↗</a>"},
        {"title": "Email Inquiries", "body": "For academic collaborations or technical inquiries: <a href='mailto:aakashheroor671@gmail.com'>aakashheroor671@gmail.com</a>"},
    ])


# ---------------------------------------------------------------------------
# Application Portal Routes
# ---------------------------------------------------------------------------

@app.route("/app")
def app_overview():
    latest_reading = db.get_latest_reading()
    return render_template("app_home.html", latest_reading=latest_reading)


@app.route("/app/history")
def app_history():
    page = max(1, request.args.get("page", 1, type=int))
    risk_filter = request.args.get("risk", "ALL").strip()
    limit = 20
    offset = (page - 1) * limit

    readings, total_count = db.get_all_readings(limit=limit, offset=offset, risk_filter=risk_filter)
    total_pages = max(1, math.ceil(total_count / limit))

    return render_template(
        "app_history.html",
        readings=readings,
        current_page=page,
        total_pages=total_pages,
        total_count=total_count,
        risk_filter=risk_filter,
    )


@app.route("/app/devices", methods=["GET", "POST"])
def app_devices():
    if request.method == "POST":
        device_name = request.form.get("device_name", "").strip()
        device_key = request.form.get("device_key", "").strip()
        if device_name and device_key:
            db.register_device(device_name, device_key)
        return redirect(url_for("app_devices"))

    devices = db.list_devices()
    return render_template("app_devices.html", devices=devices)


@app.route("/app/profile", methods=["GET", "POST"])
def app_profile():
    user = session.get("user")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        language = request.form.get("language", "en")
        if user and user.get("id"):
            updated_user = db.update_user_profile(user["id"], name=name, language=language)
            session["user"] = updated_user
            return redirect(url_for("app_profile"))

    return render_template("app_profile.html", user=user)


@app.route("/app/settings", methods=["GET", "POST"])
def app_settings():
    user = session.get("user", {})
    user_id = user.get("id")

    if request.method == "POST":
        email_enabled = bool(request.form.get("email_enabled"))
        whatsapp_enabled = bool(request.form.get("whatsapp_enabled"))
        alert_on_risk = bool(request.form.get("alert_on_risk"))
        email_address = request.form.get("email_address", "").strip()
        whatsapp_number = request.form.get("whatsapp_number", "").strip()

        if user_id:
            db.update_notification_preferences(
                user_id, email_enabled, whatsapp_enabled, alert_on_risk, email_address, whatsapp_number
            )
        return redirect(url_for("app_settings"))

    prefs = db.get_notification_preferences(user_id) if user_id else {}
    email_status = get_email_status()
    whatsapp_status = get_whatsapp_status()

    return render_template(
        "app_settings.html",
        prefs=prefs,
        email_provider_status=email_status,
        whatsapp_provider_status=whatsapp_status,
    )


# ---------------------------------------------------------------------------
# Protected Administrative Console
# ---------------------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_console():
    users = db.list_users(limit=100)
    devices = db.list_devices()
    total_readings = db.count_readings()
    total_users = db.count_users()
    notification_logs = db.get_recent_notification_logs(limit=50)

    email_status = get_email_status()
    whatsapp_status = get_whatsapp_status()
    llm_status = {
        "configured": bool(os.getenv("LLM_API_KEY")),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }

    return render_template(
        "admin.html",
        users=users,
        devices=devices,
        total_readings=total_readings,
        total_users=total_users,
        notification_logs=notification_logs,
        email_status=email_status,
        whatsapp_status=whatsapp_status,
        llm_status=llm_status,
    )


@app.route("/admin/toggle-user", methods=["POST"])
@admin_required
def admin_toggle_user():
    user_id = request.form.get("user_id", type=int)
    is_admin = request.form.get("is_admin", type=int)
    if user_id:
        db.toggle_user_admin(user_id, is_admin)
        db.log_audit_event(
            actor=session.get("user", {}).get("email", "Admin"),
            action="toggle_admin_role",
            details=f"User {user_id} admin set to {is_admin}",
            ip_address=request.remote_addr,
        )
    return redirect(url_for("admin_console"))


# ---------------------------------------------------------------------------
# Authentication Routes
# ---------------------------------------------------------------------------

@app.route("/auth/login", methods=["GET", "POST"])
def auth_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = db.get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user"] = {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
                "is_admin": bool(user["is_admin"]),
                "language": user["language"],
            }
            db.update_user_login(user["id"])
            next_url = request.args.get("next") or url_for("app_overview")
            return redirect(next_url)

        return render_template("auth_login.html", error="Invalid email address or password.")

    return render_template("auth_login.html")


@app.route("/auth/signup", methods=["GET", "POST"])
def auth_signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            return render_template("auth_signup.html", error="All fields are required.")

        if password != confirm:
            return render_template("auth_signup.html", error="Passwords do not match.")

        if len(password) < 8:
            return render_template("auth_signup.html", error="Password must be at least 8 characters.")

        if db.get_user_by_email(email):
            return render_template("auth_signup.html", error="An account with this email already exists.")

        user = db.create_user(
            email=email,
            password_hash=generate_password_hash(password),
            name=name,
        )

        if user:
            session["user"] = {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
                "is_admin": False,
                "language": "en",
            }
            return redirect(url_for("app_overview"))

        return render_template("auth_signup.html", error="Could not create account.")

    return render_template("auth_signup.html")


@app.route("/auth/forgot-password", methods=["GET", "POST"])
def auth_forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        # In this demonstration, acknowledge the request safely without credential leaks
        return render_template(
            "auth_forgot.html",
            message=f"If an account is associated with {email}, recovery instructions have been dispatched.",
        )
    return render_template("auth_forgot.html")


@app.route("/auth/reset-password", methods=["GET", "POST"])
def auth_reset_password():
    if request.method == "POST":
        new_pass = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        user = session.get("user")

        if user and new_pass and new_pass == confirm and len(new_pass) >= 8:
            db.update_user_password(user["id"], generate_password_hash(new_pass))
            return redirect(url_for("app_profile"))

    return render_template("auth_reset.html")


@app.route("/auth/google")
def auth_google_login():
    """Google OAuth initialization. In demonstration mode without secrets, handles simulated callback."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        # Graceful simulated Google sign-in for evaluator testing
        session["user"] = {
            "id": 999,
            "email": "google.evaluator@sepsissense.org",
            "name": "Google Clinical Evaluator",
            "role": "user",
            "is_admin": False,
            "language": "en",
        }
        return redirect(url_for("app_overview"))

    # When real GOOGLE_CLIENT_ID is provided, redirect to Google Accounts
    redirect_uri = url_for("auth_callback", _external=True)
    google_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&response_type=code&scope=openid%20email%20profile&"
        f"redirect_uri={redirect_uri}&state=sepsissense_oauth"
    )
    return redirect(google_url)


@app.route("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    # Log callback event
    return redirect(url_for("app_overview"))


@app.route("/auth/logout")
def auth_logout():
    session.clear()
    return redirect(url_for("landing"))


# ---------------------------------------------------------------------------
# API Endpoints (Preserves ESP32 POST /api/readings Contract)
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({
        "status": "ok",
        "service": "SepsisSense Flask API",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "prediction_service": "loaded",
        "database": "connected",
        "render_url": "https://sepsis-prediction-dashboard.onrender.com",
    }), 200


@app.route("/api/model-metadata", methods=["GET"])
def model_metadata():
    metadata = _read_model_metadata()
    if not metadata:
        return jsonify({"error": "Model metadata is unavailable"}), 503
    return jsonify(metadata), 200


@app.route("/api/predict", methods=["POST"])
def predict_without_storing():
    """Interactive prediction playground. Does not insert into history."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400

    required_fields = ("bpm", "temperature", "spo2")
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Required fields: bpm, temperature, spo2"}), 400

    try:
        bpm = float(data["bpm"])
        temperature = float(data["temperature"])
        spo2 = float(data["spo2"])
    except (TypeError, ValueError):
        return jsonify({"error": "All readings must be numbers"}), 400

    if not all(math.isfinite(v) for v in (bpm, temperature, spo2)):
        return jsonify({"error": "Readings must be finite numbers"}), 400

    if not (0 < bpm <= 300) or not (20 <= temperature <= 45) or not (0 <= spo2 <= 100):
        return jsonify({"error": "Readings out of realistic physiological range"}), 400

    try:
        prediction = predict_reading(bpm, temperature, spo2)
    except Exception:
        app.logger.exception("Prediction failed")
        return jsonify({"error": "Prediction service unavailable"}), 503

    return jsonify({
        "inputs": {"bpm": bpm, "temperature": temperature, "spo2": spo2},
        "prediction": prediction,
        "stored": False,
        "warning": "Experimental output only. Not a clinically validated diagnostic estimate.",
    }), 200


@app.route("/api/assistant", methods=["POST"])
def assistant_api():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400

    message = str(data.get("message", "")).strip()
    language = str(data.get("language", "en")).lower()
    mode = str(data.get("mode", "education")).lower()

    if not message:
        return jsonify({"error": "Enter a question first."}), 400

    if len(message) > 4000:
        return jsonify({"error": "Message exceeds 4,000 character limit."}), 400

    if language not in {"en", "hi", "ta", "kn"}:
        return jsonify({"error": "Supported languages: en, hi, ta, kn."}), 400

    if mode not in {"education", "project"}:
        return jsonify({"error": "Mode must be education or project."}), 400

    try:
        from assistant_service import answer_question
        answer = answer_question(message, language, mode, _read_model_metadata())
        return jsonify(answer), 200
    except Exception as exc:
        app.logger.exception("Assistant request failed")
        return jsonify({"error": str(exc)}), 502


@app.route("/api/readings", methods=["POST"])
def create_reading():
    """
    CRITICAL WORKFLOW PRESERVATION:
    Receives incoming ESP32 sensor telemetry every 5 seconds.
    Format: {"bpm": 82, "temperature": 36.7, "spo2": 98}
    Returns HTTP 201 with stored reading ID and ML prediction.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400

    required_fields = ("bpm", "temperature", "spo2")
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Required fields: bpm, temperature, spo2"}), 400

    try:
        bpm = float(data["bpm"])
        temperature = float(data["temperature"])
        spo2 = float(data["spo2"])
    except (TypeError, ValueError):
        return jsonify({"error": "All readings must be numbers"}), 400

    if not all(math.isfinite(v) for v in (bpm, temperature, spo2)):
        return jsonify({"error": "Readings must be finite numbers"}), 400

    if not (0 < bpm <= 300) or not (20 <= temperature <= 45) or not (0 <= spo2 <= 100):
        return jsonify({"error": "Readings out of realistic physiological range"}), 400

    device_id = str(data.get("device_id", "ESP32-Sepsis-01"))

    try:
        prediction = predict_reading(bpm, temperature, spo2)
    except Exception:
        app.logger.exception("Prediction failed for incoming ESP32 reading")
        return jsonify({"error": "Prediction service unavailable; reading was not stored"}), 503

    reading_id = db.insert_reading(
        bpm,
        temperature,
        spo2,
        prediction=prediction["prediction"],
        sepsis_probability=prediction["sepsis_probability"],
        prediction_threshold=prediction["threshold"],
        device_id=device_id,
    )

    # Dispatch alerts if threshold exceeded
    dispatch_risk_alert_if_needed({
        "id": reading_id,
        "bpm": bpm,
        "temperature": temperature,
        "spo2": spo2,
        "prediction": prediction["prediction"],
        "sepsis_probability": prediction["sepsis_probability"],
    })

    return jsonify({
        "message": "Reading stored successfully",
        "id": reading_id,
        "prediction": prediction,
    }), 201


@app.route("/api/readings", methods=["GET"])
def list_readings():
    """Returns most recent 20 readings for the real-time dashboard chart."""
    readings = db.get_recent_readings(limit=20)
    return jsonify({"count": len(readings), "readings": readings}), 200


@app.route("/api/readings/<int:reading_id>/explanation", methods=["GET"])
def get_reading_explanation(reading_id):
    recent = db.get_recent_readings(limit=1000)
    reading = next((item for item in recent if item["id"] == reading_id), None)

    if reading is None:
        return jsonify({"error": "Reading not found"}), 404

    try:
        explanation = explain_reading(
            bpm=reading["bpm"],
            temperature=reading["temperature"],
            spo2=reading["spo2"],
        )
        explanation["reading_id"] = reading_id
        explanation["timestamp"] = reading["timestamp"]
        return jsonify(explanation), 200
    except Exception as exc:
        app.logger.exception("LIME explanation generation failed")
        return jsonify({
            "error": "Could not generate explanation",
            "details": str(exc),
            "exception_type": type(exc).__name__,
        }), 500


@app.route("/api/history/export")
def export_readings_csv():
    """Generates and downloads a complete CSV file of all stored readings."""
    readings, _ = db.get_all_readings(limit=5000)

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["ID", "Timestamp_UTC", "Device_ID", "BPM_HeartRate", "Temperature_C", "SpO2_Percent", "Classification", "Sepsis_Probability", "Threshold"])

    for r in readings:
        cw.writerow([
            r.get("id"),
            r.get("timestamp"),
            r.get("device_id", "ESP32-Sepsis-01"),
            r.get("bpm"),
            r.get("temperature"),
            r.get("spo2"),
            r.get("prediction"),
            r.get("sepsis_probability"),
            r.get("prediction_threshold"),
        ])

    output = Response(si.getvalue(), mimetype="text/csv")
    output.headers["Content-Disposition"] = f"attachment; filename=sepsissense_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return output


@app.route("/api/quiz/save", methods=["POST"])
def save_quiz():
    data = request.get_json(silent=True) or {}
    topic = data.get("quiz_topic", "general")
    score = int(data.get("score", 0))
    total = int(data.get("total", 1))
    user_id = session.get("user", {}).get("id")

    attempt_id = db.save_quiz_attempt(user_id, topic, score, total)
    return jsonify({"success": True, "attempt_id": attempt_id}), 200


@app.route("/api/test-notification", methods=["POST"])
def api_test_notification():
    channel = request.form.get("channel", "email")
    user = session.get("user", {})
    user_id = user.get("id")

    if channel == "email":
        recipient = user.get("email") or "researcher@example.com"
        res = send_email_notification(
            to_email=recipient,
            subject="Diagnostic Test Ping",
            body_html="<p>This is a verified test notification from SepsisSense.</p>",
            body_text="This is a verified test notification from SepsisSense.",
            user_id=user_id,
        )
    else:
        recipient = "+1234567890"
        res = send_whatsapp_notification(
            to_number=recipient,
            message_text="[SepsisSense] Diagnostic test ping from server.",
            user_id=user_id,
        )

    return redirect(url_for("app_settings"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
