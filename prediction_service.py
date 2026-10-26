
import json
from pathlib import Path

import joblib
import pandas as pd


# Existing ML project: read its artifacts without modifying them.
ML_ROOT = Path(
    r"C:\Users\prate\Downloads\Early_Sepsis_Prediction"
)

MODEL_PATH = (
    ML_ROOT
    / "module2_ml"
    / "sensor_random_forest_pipeline.joblib"
)
METADATA_PATH = (
    ML_ROOT
    / "module2_ml"
    / "sensor_model_metadata.json"
)

FEATURES = ["HR", "O2Sat", "Temp"]


def load_model_artifacts():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Sensor model not found: {MODEL_PATH}"
        )

    if not METADATA_PATH.is_file():
        raise FileNotFoundError(
            f"Sensor model metadata not found: {METADATA_PATH}"
        )

    with METADATA_PATH.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    if metadata.get("features") != FEATURES:
        raise ValueError(
            "Model metadata feature order does not match "
            f"the expected features: {FEATURES}"
        )

    model = joblib.load(MODEL_PATH)

    if list(model.feature_names_in_) != FEATURES:
        raise ValueError(
            "Saved model feature order does not match "
            f"the expected features: {FEATURES}"
        )

    threshold = float(metadata["selected_threshold"])

    if not 0.0 <= threshold <= 1.0:
        raise ValueError("Invalid model threshold in metadata.")

    return model, threshold


# Load once when the service module is imported.
_model, _threshold = load_model_artifacts()


def predict_reading(bpm, temperature, spo2):
    """Return an experimental prediction for one sensor reading."""

    input_data = pd.DataFrame(
        [[float(bpm), float(spo2), float(temperature)]],
        columns=FEATURES,
    )

    probabilities = _model.predict_proba(input_data)[0]
    sepsis_probability = float(probabilities[1])

    prediction_value = int(sepsis_probability >= _threshold)

    return {
        "prediction": (
            "SEPSIS_RISK_FLAG"
            if prediction_value == 1
            else "NO_RISK_FLAG"
        ),
        "prediction_value": prediction_value,
        "sepsis_probability": sepsis_probability,
        "threshold": _threshold,
        "experimental": True,
        "warning": (
            "Experimental model output, not a diagnosis "
            "or a clinically validated risk estimate."
        ),
    }
