
import sqlite3

DATABASE_NAME = "sepsis.db"


def initialize_database():
    """Create the readings table and safely add prediction columns."""
    with sqlite3.connect(DATABASE_NAME) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                bpm REAL,
                temperature REAL,
                spo2 REAL
            )
        """)

        # Migrate existing databases without deleting their records.
        existing_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(sensor_readings)"
            ).fetchall()
        }

        new_columns = {
            "prediction": "TEXT",
            "sepsis_probability": "REAL",
            "prediction_threshold": "REAL",
        }

        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE sensor_readings "
                    f"ADD COLUMN {column_name} {column_type}"
                )


def insert_reading(
    bpm,
    temperature,
    spo2,
    prediction=None,
    sepsis_probability=None,
    prediction_threshold=None,
):
    """Store a reading and its optional prediction; return its ID."""
    with sqlite3.connect(DATABASE_NAME) as connection:
        cursor = connection.execute("""
            INSERT INTO sensor_readings (
                bpm,
                temperature,
                spo2,
                prediction,
                sepsis_probability,
                prediction_threshold
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            bpm,
            temperature,
            spo2,
            prediction,
            sepsis_probability,
            prediction_threshold,
        ))

        return cursor.lastrowid


def get_latest_reading():
    """Return the newest reading, or None if the table is empty."""
    with sqlite3.connect(DATABASE_NAME) as connection:
        connection.row_factory = sqlite3.Row

        reading = connection.execute("""
            SELECT *
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        return dict(reading) if reading else None


def get_recent_readings(limit=20):
    """Return the most recent readings, newest first."""
    with sqlite3.connect(DATABASE_NAME) as connection:
        connection.row_factory = sqlite3.Row

        readings = connection.execute("""
            SELECT *
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(reading) for reading in readings]


if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")
    print("Latest reading:", get_latest_reading())
