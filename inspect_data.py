
import sqlite3

connection = sqlite3.connect("sepsis.db")

rows = connection.execute("""
    SELECT id, timestamp, bpm, temperature, spo2
    FROM sensor_readings
    ORDER BY id ASC
""").fetchall()

print(f"Total records: {len(rows)}")
print()

for row in rows:
    print(
        f"ID: {row[0]} | "
        f"Timestamp: {row[1]} | "
        f"BPM: {row[2]} | "
        f"Temperature: {row[3]} | "
        f"SpO2: {row[4]}"
    )

connection.close()
