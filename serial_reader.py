
import re
import time
from dataclasses import dataclass, field


FRESHNESS_WINDOW_SECONDS = 5.0


@dataclass
class SensorReadings:
    bpm: float | None = None
    temperature: float | None = None
    spo2: float | None = None

    updated_at: dict[str, float] = field(default_factory=dict)

    def update(self, name: str, value: float) -> None:
        setattr(self, name, value)
        self.updated_at[name] = time.monotonic()

    def complete(self) -> bool:
        return all(
            getattr(self, name) is not None
            for name in ("bpm", "temperature", "spo2")
        )

    def fresh(self, now: float | None = None) -> bool:
        if not self.complete():
            return False

        now = time.monotonic() if now is None else now

        timestamps = [
            self.updated_at.get(name, 0.0)
            for name in ("bpm", "temperature", "spo2")
        ]

        if any(timestamp == 0.0 for timestamp in timestamps):
            return False

        return (
            max(timestamps) - min(timestamps)
            <= FRESHNESS_WINDOW_SECONDS
            and all(
                now - timestamp <= FRESHNESS_WINDOW_SECONDS
                for timestamp in timestamps
            )
        )

    def valid(self) -> bool:
        return (
            self.complete()
            and 0 < self.bpm <= 250
            and -20 <= self.temperature <= 100
            and 0 <= self.spo2 <= 100
        )

    def as_dict(self) -> dict:
        return {
            "bpm": self.bpm,
            "temperature": self.temperature,
            "spo2": self.spo2,
        }


def parse_line(line: str, readings: SensorReadings) -> None:
    """Parse fields found on a single ESP32 serial-output line."""

    bpm_match = re.search(
        r"\bBPM\s*[:=]\s*(\d+(?:\.\d+)?)",
        line,
        re.IGNORECASE,
    )
    if bpm_match:
        readings.update("bpm", float(bpm_match.group(1)))

    temperature_match = re.search(
        r"\btemperature\s*[:=]\s*(-?\d+(?:\.\d+)?)",
        line,
        re.IGNORECASE,
    )
    if temperature_match:
        readings.update(
            "temperature",
            float(temperature_match.group(1)),
        )

    spo2_match = re.search(
        r"\bsp\s*o?\s*2\s*[:=]\s*(\d+(?:\.\d+)?)\s*%?",
        line,
        re.IGNORECASE,
    )
    if spo2_match:
        readings.update("spo2", float(spo2_match.group(1)))


def validate_readings(readings: SensorReadings) -> bool:
    return readings.valid() and readings.fresh()


def run_parser_test() -> None:
    readings = SensorReadings()

    # Synthetic test data; no hardware is connected.
    samples = [
        "ets Jul 29 2019 12:21:46",
        "temperature = 20.39 Â°C ,",
        "BPM = 71 , BPM = 71 , spO2 = 95%",
        " spo2 = 96% ,Temperature = 34Â°C,Glucose = 90 mg/dL",
    ]

    for line in samples:
        parse_line(line, readings)
        print(f"Input: {line}")

    print("\nParsed values:", readings.as_dict())
    print("Complete:", readings.complete())
    print("Fresh:", readings.fresh())
    print("Valid and fresh:", validate_readings(readings))

    # Confirm stale data is rejected.
    old_time = time.monotonic() - 10

    stale = SensorReadings(
        bpm=71,
        temperature=34,
        spo2=96,
        updated_at={
            "bpm": old_time,
            "temperature": old_time,
            "spo2": old_time,
        },
    )

    print("Stale test accepted:", validate_readings(stale))
    assert not validate_readings(stale)
    print("\nFreshness test passed.")


if __name__ == "__main__":
    run_parser_test()
