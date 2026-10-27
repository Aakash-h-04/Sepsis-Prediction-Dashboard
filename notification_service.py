"""
SepsisSense Notification Service
Handles email notifications (via Gmail API / SMTP) and WhatsApp notifications (via Twilio).
Server-side credentials only. Fails gracefully with explicit status when unconfigured.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import base64
import json

from database import log_notification_event


def get_email_status():
    """Returns whether email delivery is configured and provider details."""
    gmail_token = os.getenv("GMAIL_REFRESH_TOKEN") or os.getenv("GMAIL_API_KEY")
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")

    if gmail_token:
        return {"configured": True, "provider": "Gmail API", "sender": os.getenv("GMAIL_SENDER", "notifications@sepsissense.org")}
    if smtp_host and smtp_user:
        return {"configured": True, "provider": f"SMTP ({smtp_host})", "sender": smtp_user}
    return {
        "configured": False,
        "provider": "None",
        "message": "Neither Gmail API nor SMTP credentials are set in environment.",
    }


def get_whatsapp_status():
    """Returns whether Twilio WhatsApp delivery is configured."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER")

    if account_sid and auth_token and from_number:
        return {
            "configured": True,
            "provider": "Twilio WhatsApp",
            "from_number": from_number,
        }
    return {
        "configured": False,
        "provider": "None",
        "message": "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_WHATSAPP_NUMBER not set.",
    }


def send_email_notification(to_email, subject, body_html, body_text="", user_id=None):
    """
    Sends an email notification if configured, logging the result.
    Does not crash if provider credentials are absent.
    """
    if not to_email:
        return {"success": False, "error": "Recipient email address is required."}

    status = get_email_status()
    if not status["configured"]:
        log_notification_event(
            user_id=user_id,
            channel="email",
            event_type=subject[:50],
            recipient=to_email,
            status="unconfigured",
            error_details="Email provider not configured in environment.",
        )
        return {
            "success": False,
            "error": "Email provider is not configured. Set GMAIL or SMTP variables.",
            "unconfigured": True,
        }

    # Attempt SMTP send if SMTP is set
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if smtp_host and smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[SepsisSense] {subject}"
            msg["From"] = smtp_user
            msg["To"] = to_email

            if body_text:
                msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_email], msg.as_string())

            log_notification_event(user_id, "email", subject[:50], to_email, "delivered")
            return {"success": True, "message": "Email delivered successfully via SMTP."}
        except Exception as exc:
            log_notification_event(user_id, "email", subject[:50], to_email, "failed", str(exc))
            return {"success": False, "error": f"SMTP delivery failed: {exc}"}

    # Gmail API placeholder (requires OAuth token)
    log_notification_event(user_id, "email", subject[:50], to_email, "unconfigured", "Gmail API credentials pending token exchange.")
    return {"success": False, "error": "Gmail API requires refresh token exchange."}


def send_whatsapp_notification(to_number, message_text, user_id=None):
    """
    Sends a WhatsApp message via Twilio REST API if configured, logging the result.
    """
    if not to_number:
        return {"success": False, "error": "Recipient phone number is required."}

    status = get_whatsapp_status()
    if not status["configured"]:
        log_notification_event(
            user_id=user_id,
            channel="whatsapp",
            event_type="alert",
            recipient=to_number,
            status="unconfigured",
            error_details="Twilio credentials not configured in environment.",
        )
        return {
            "success": False,
            "error": "Twilio WhatsApp is not configured in the server environment.",
            "unconfigured": True,
        }

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"

    target_number = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    auth_header = "Basic " + base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("utf-8")

    payload = urlencode({
        "From": from_number,
        "To": target_number,
        "Body": message_text,
    }).encode("utf-8")

    req = Request(url, data=payload, headers={
        "Authorization": auth_header,
        "Content-Type": "application/x-www-form-urlencoded",
    }, method="POST")

    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sid = data.get("sid", "unknown")
            log_notification_event(user_id, "whatsapp", "alert", to_number, "delivered", f"Twilio SID: {sid}")
            return {"success": True, "message": "WhatsApp alert delivered.", "sid": sid}
    except HTTPError as exc:
        err = f"Twilio HTTP {exc.code}"
        log_notification_event(user_id, "whatsapp", "alert", to_number, "failed", err)
        return {"success": False, "error": err}
    except Exception as exc:
        log_notification_event(user_id, "whatsapp", "alert", to_number, "failed", str(exc))
        return {"success": False, "error": f"WhatsApp send failed: {exc}"}


def dispatch_risk_alert_if_needed(reading):
    """
    If reading triggered SEPSIS_RISK_FLAG, logs the system event.
    Note: Does not spam notifications or claim clinical certainty.
    """
    if reading.get("prediction") == "SEPSIS_RISK_FLAG":
        bpm = reading.get("bpm")
        temp = reading.get("temperature")
        spo2 = reading.get("spo2")
        prob = reading.get("sepsis_probability", 0)

        # Log an internal event for dashboard review
        log_notification_event(
            user_id=None,
            channel="system",
            event_type="risk_flag_logged",
            recipient="dashboard_event_stream",
            status="logged",
            error_details=f"Experimental flag: HR={bpm}, Temp={temp}, SpO2={spo2}, prob={prob:.3f}",
        )
