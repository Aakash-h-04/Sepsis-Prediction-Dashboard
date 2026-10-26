
import re
import sys
import time
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import serial

from serial_reader import (
    SensorReadings,
    parse_line,
    validate_readings,
)

API_URL = "http://127.0.0.1:5000/api/readings"
BAUD_RATE = 115200

REQUIRED_FIELDS = {"bpm", "temperature", "spo2"}


def post_reading(readings: SensorReadings) -> bool:
    """Send one validated reading to Flask."""
    payload = json.dumps(readings.as_dict()).encode("utf-8")

    request = Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=5) as response:
            print(f"Flask accepted reading: HTTP {response.status}")
            return 200 <= response.status < 300

    except HTTPError as error:
        print(f"Flask rejected reading: HTTP {error.code}")
        print(error.read().decode("utf-8", errors="replace"))

    except (URLError, TimeoutError, OSError) as error:
        print(f"Could not reach Flask: {error}")

    return False


def has_bpm_and_spo2(line: str) -> bool:
    """Return True only if both fields occur on this same line."""
    has_bpm = re.search(
        r"\bBPM\s*[:=]\s*\d+(?:\.\d+)?",
        line,
        re.IGNORECASE,
    )

    has_spo2 = re.search(
        r"\bsp\s*o?\s*2\s*[:=]\s*\d+(?:\.\d+)?\s*%?",
        line,
        re.IGNORECASE,
    )

    return bool(has_bpm and has_spo2)


def run_serial_reader(port: str) -> None:
    readings = SensorReadings()

    # Track fields updated since the last successful POST.
    updated_since_submission = set()

    print(f"Opening {port} at {BAUD_RATE} baud...")
    print(f"Sending readings to {API_URL}")
    print("Submissions require new BPM, temperature, and SpO2 values.")
    print("Press Ctrl+C to stop.\n")

    try:
        with serial.Serial(port, BAUD_RATE, timeout=1) as device:
            # Allow the board to settle after opening its serial port.
            time.sleep(2)
            device.reset_input_buffer()

            while True:
                raw_line = device.readline()

                if not raw_line:
                    continue

                line = raw_line.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

                if not line:
                    continue

                print(f"ESP32: {line}")

                # Record which fields were updated by this line.
                previous_updated_at = dict(readings.updated_at)
                parse_line(line, readings)

                for field_name in REQUIRED_FIELDS:
                    if (
                        readings.updated_at.get(field_name)
                        != previous_updated_at.get(field_name)
                    ):
                        updated_since_submission.add(field_name)

                # Only a line containing both BPM and SpO2
                # can trigger a submission.
                if not has_bpm_and_spo2(line):
                    continue

                if updated_since_submission != REQUIRED_FIELDS:
                    print(
                        "Skipping: waiting for new BPM, temperature, "
                        "and SpO2 values."
                    )
                    continue

                if not readings.complete():
                    print("Skipping: one or more vitals are missing.")
                    continue

                if not readings.fresh():
                    print(
                        "Skipping: readings are stale or too far apart. "
                        "Waiting for fresh measurements."
                    )
                    continue

                if not validate_readings(readings):
                    print("Skipping: values failed basic validation.")
                    continue

                print(
                    "Submitting fresh candidate:",
                    readings.as_dict(),
                )

                # Reset tracking only after a successful POST.
                if post_reading(readings):
                    updated_since_submission.clear()

    except serial.SerialException as error:
        print(f"Serial connection error: {error}")
        print("Check the COM port, USB connection, and baud rate.")

    except KeyboardInterrupt:
        print("\nSerial reader stopped.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python serial_to_flask.py COM5")
        raise SystemExit(1)

    run_serial_reader(sys.argv[1])
