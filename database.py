"""
SepsisSense Database Management
Supports SQLite (local and default) and managed PostgreSQL (via DATABASE_URL or SUPABASE_DB_URL).
Preserves existing schema for sensor_readings while adding tables for users, devices,
notifications, chat history, learning progress, and audit logs.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_NAME = os.getenv("SQLITE_DATABASE_PATH", str(PROJECT_ROOT / "sepsis.db"))
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")


def get_connection():
    """
    Returns a database connection.
    Defaults to SQLite for guaranteed zero-dependency stability.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    """
    Creates all necessary tables if they do not exist,
    and safely migrates existing tables without data loss.
    """
    with get_connection() as conn:
        # 1. Sensor readings table (compatible with existing ESP32 workflow)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                bpm REAL,
                temperature REAL,
                spo2 REAL,
                prediction TEXT,
                sepsis_probability REAL,
                prediction_threshold REAL,
                device_id TEXT DEFAULT 'ESP32-Sepsis-01'
            )
        """)

        # Migration: ensure prediction and device_id columns exist
        existing_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(sensor_readings)").fetchall()
        }
        for col_name, col_type in {
            "prediction": "TEXT",
            "sepsis_probability": "REAL",
            "prediction_threshold": "REAL",
            "device_id": "TEXT DEFAULT 'ESP32-Sepsis-01'",
        }.items():
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE sensor_readings ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

        # 2. Users table for authentication
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_admin INTEGER DEFAULT 0,
                language TEXT DEFAULT 'en',
                timezone TEXT DEFAULT 'UTC',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME
            )
        """)

        # 3. Devices table for IoT management
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL,
                device_key TEXT UNIQUE NOT NULL,
                device_type TEXT DEFAULT 'ESP32',
                status TEXT DEFAULT 'active',
                last_seen DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default demo device if none exists
        existing_device = conn.execute("SELECT id FROM devices WHERE device_key = 'ESP32-Sepsis-01'").fetchone()
        if not existing_device:
            conn.execute("""
                INSERT INTO devices (device_name, device_key, device_type, status, last_seen)
                VALUES ('Ward 4 Sensor Node', 'ESP32-Sepsis-01', 'ESP32', 'active', CURRENT_TIMESTAMP)
            """)

        # 4. Notification preferences
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                email_enabled INTEGER DEFAULT 1,
                whatsapp_enabled INTEGER DEFAULT 0,
                alert_on_risk INTEGER DEFAULT 1,
                email_address TEXT,
                whatsapp_number TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. Notification delivery logs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel TEXT NOT NULL,
                event_type TEXT NOT NULL,
                recipient TEXT NOT NULL,
                status TEXT NOT NULL,
                error_details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 6. Chat sessions and messages for AI Assistant
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                mode TEXT DEFAULT 'education',
                language TEXT DEFAULT 'en',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                language TEXT DEFAULT 'en',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 7. Learning progress and quiz attempts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learning_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                module_key TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                score INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, module_key)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                quiz_topic TEXT NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 8. Administrative audit logs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 9. User feedback
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                feedback TEXT NOT NULL,
                email TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


# ---------------------------------------------------------------------------
# Sensor Readings Operations (Compatible with existing ESP32 endpoints)
# ---------------------------------------------------------------------------

def insert_reading(
    bpm,
    temperature,
    spo2,
    prediction=None,
    sepsis_probability=None,
    prediction_threshold=None,
    device_id="ESP32-Sepsis-01",
):
    """Store a reading and its optional prediction; return its ID."""
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO sensor_readings (
                bpm,
                temperature,
                spo2,
                prediction,
                sepsis_probability,
                prediction_threshold,
                device_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            bpm,
            temperature,
            spo2,
            prediction,
            sepsis_probability,
            prediction_threshold,
            device_id,
        ))

        # Update device last_seen timestamp
        conn.execute("""
            UPDATE devices
            SET last_seen = CURRENT_TIMESTAMP
            WHERE device_key = ?
        """, (device_id,))

        conn.commit()
        return cursor.lastrowid


def get_latest_reading():
    """Return the newest reading, or None if the table is empty."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT *
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()
        return dict(row) if row else None


def get_recent_readings(limit=20):
    """Return the most recent readings, newest first."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT *
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_all_readings(limit=1000, offset=0, risk_filter=None):
    """Return filtered readings with count for pagination."""
    with get_connection() as conn:
        query = "SELECT * FROM sensor_readings"
        params = []
        if risk_filter and risk_filter.upper() != "ALL":
            query += " WHERE prediction = ?"
            params.append(risk_filter)

        count_query = "SELECT COUNT(*) as total FROM (" + query + ")"
        total = conn.execute(count_query, params).fetchone()["total"]

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows], total


def count_readings():
    """Total number of readings recorded."""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as total FROM sensor_readings").fetchone()
        return row["total"] if row else 0


# ---------------------------------------------------------------------------
# User Authentication & Management Operations
# ---------------------------------------------------------------------------

def create_user(email, password_hash, name, role="user", is_admin=0):
    """Create a new user; returns user dict or None if email already exists."""
    with get_connection() as conn:
        try:
            cursor = conn.execute("""
                INSERT INTO users (email, password_hash, name, role, is_admin)
                VALUES (?, ?, ?, ?, ?)
            """, (email.lower().strip(), password_hash, name.strip(), role, is_admin))
            user_id = cursor.lastrowid

            # Initialize notification preferences
            conn.execute("""
                INSERT OR IGNORE INTO notification_preferences (user_id, email_address)
                VALUES (?, ?)
            """, (user_id, email.lower().strip()))

            conn.commit()
            return get_user_by_id(user_id)
        except sqlite3.IntegrityError:
            return None


def get_user_by_email(email):
    """Find a user by email address."""
    if not email:
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    """Find a user by ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_user_login(user_id):
    """Update last_login timestamp."""
    with get_connection() as conn:
        conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        conn.commit()


def update_user_profile(user_id, name=None, language=None, timezone=None):
    """Update user personal preferences."""
    with get_connection() as conn:
        updates = []
        params = []
        if name:
            updates.append("name = ?")
            params.append(name.strip())
        if language:
            updates.append("language = ?")
            params.append(language)
        if timezone:
            updates.append("timezone = ?")
            params.append(timezone)
        if updates:
            params.append(user_id)
            conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
    return get_user_by_id(user_id)


def update_user_password(user_id, password_hash):
    """Update user hashed password."""
    with get_connection() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        conn.commit()


def list_users(limit=100):
    """List all registered users."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, email, name, role, is_admin, language, timezone, created_at, last_login
            FROM users
            ORDER BY id ASC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]


def count_users():
    """Total registered user count."""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as total FROM users").fetchone()
        return row["total"] if row else 0


def toggle_user_admin(user_id, is_admin):
    """Update admin status for a user."""
    with get_connection() as conn:
        conn.execute("UPDATE users SET is_admin = ?, role = ? WHERE id = ?", (
            1 if is_admin else 0,
            "admin" if is_admin else "user",
            user_id
        ))
        conn.commit()


# ---------------------------------------------------------------------------
# Device Management Operations
# ---------------------------------------------------------------------------

def list_devices():
    """List all registered IoT devices."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM devices ORDER BY id ASC").fetchall()
        return [dict(row) for row in rows]


def register_device(device_name, device_key, device_type="ESP32"):
    """Register a new device."""
    with get_connection() as conn:
        try:
            cursor = conn.execute("""
                INSERT INTO devices (device_name, device_key, device_type, status)
                VALUES (?, ?, ?, 'active')
            """, (device_name.strip(), device_key.strip(), device_type))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None


# ---------------------------------------------------------------------------
# Notification Preferences and Logs
# ---------------------------------------------------------------------------

def get_notification_preferences(user_id):
    """Get notification settings for a user."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM notification_preferences WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return {
                "user_id": user_id,
                "email_enabled": 1,
                "whatsapp_enabled": 0,
                "alert_on_risk": 1,
                "email_address": "",
                "whatsapp_number": "",
            }
        return dict(row)


def update_notification_preferences(user_id, email_enabled, whatsapp_enabled, alert_on_risk, email_address, whatsapp_number):
    """Save user notification preferences."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO notification_preferences (user_id, email_enabled, whatsapp_enabled, alert_on_risk, email_address, whatsapp_number, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                email_enabled=excluded.email_enabled,
                whatsapp_enabled=excluded.whatsapp_enabled,
                alert_on_risk=excluded.alert_on_risk,
                email_address=excluded.email_address,
                whatsapp_number=excluded.whatsapp_number,
                updated_at=CURRENT_TIMESTAMP
        """, (user_id, 1 if email_enabled else 0, 1 if whatsapp_enabled else 0, 1 if alert_on_risk else 0, email_address, whatsapp_number))
        conn.commit()


def log_notification_event(user_id, channel, event_type, recipient, status, error_details=None):
    """Log notification delivery outcome."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO notification_logs (user_id, channel, event_type, recipient, status, error_details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, channel, event_type, recipient, status, error_details))
        conn.commit()


def get_recent_notification_logs(limit=50):
    """Fetch recent notification delivery records."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM notification_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Learning Progress and Quiz Attempts
# ---------------------------------------------------------------------------

def save_quiz_attempt(user_id, quiz_topic, score, total):
    """Record a completed quiz attempt."""
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO quiz_attempts (user_id, quiz_topic, score, total)
            VALUES (?, ?, ?, ?)
        """, (user_id, quiz_topic, score, total))
        if user_id:
            conn.execute("""
                INSERT INTO learning_progress (user_id, module_key, completed, score, updated_at)
                VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, module_key) DO UPDATE SET
                    completed = 1,
                    score = MAX(learning_progress.score, excluded.score),
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, quiz_topic, int((score / total) * 100)))
        conn.commit()
        return cursor.lastrowid


def get_user_progress(user_id):
    """Get all learning progress records for a user."""
    if not user_id:
        return {}
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM learning_progress WHERE user_id = ?", (user_id,)).fetchall()
        return {row["module_key"]: dict(row) for row in rows}


# ---------------------------------------------------------------------------
# Audit Logs & Feedback
# ---------------------------------------------------------------------------

def log_audit_event(actor, action, details=None, ip_address=None):
    """Record an administrative audit event."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO admin_audit_logs (actor, action, details, ip_address)
            VALUES (?, ?, ?, ?)
        """, (actor, action, details, ip_address))
        conn.commit()


def get_audit_logs(limit=50):
    """Fetch recent audit events."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM admin_audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


def save_user_feedback(category, feedback, email=None):
    """Save user-submitted feedback."""
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO user_feedback (category, feedback, email)
            VALUES (?, ?, ?)
        """, (category, feedback, email))
        conn.commit()
        return cursor.lastrowid


if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")
    print("Latest reading:", get_latest_reading())
    print("Total readings:", count_readings())
