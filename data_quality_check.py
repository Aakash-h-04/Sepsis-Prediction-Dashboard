
import sqlite3
from pathlib import Path

DATABASE_NAME = Path(__file__).parent / "sepsis.db"

# These records have uncertain provenance based on our discussion.
UNCERTAIN_PROVENANCE_IDS = {1, 2, 3}


def main():
    with sqlite3.connect(DATABASE_NAME) as connection:
        rows = connection.execute("""
            SELECT id, timestamp, bpm, temperature, spo2
            FROM sensor_readings
            ORDER BY id
        """).fetchall()

    print(f"Total records inspected: {len(rows)}")
    print("=" * 65)

    for record_id, timestamp, bpm, temperature, spo2 in rows:
        flags = []

        if record_id in UNCERTAIN_PROVENANCE_IDS:
            flags.append("PROVENANCE UNCERTAIN")

        if temperature < 30 or temperature > 45:
            flags.append("TEMPERATURE NEEDS INVESTIGATION")

        if bpm < 30 or bpm > 220:
            flags.append("BPM NEEDS INVESTIGATION")

        if spo2 < 0 or spo2 > 100:
            flags.append("SPO2 OUTSIDE NUMERICAL RANGE")

        status = "; ".join(flags) if flags else "NO AUTOMATED FLAG"

        print(
            f"ID {record_id} | {timestamp}\n"
            f"  BPM={bpm}, Temp={temperature}, SpO2={spo2}\n"
            f"  Review: {status}\n"
        )


if __name__ == "__main__":
    main()
