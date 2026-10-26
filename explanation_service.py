
import json
from pathlib import Path
from threading import Lock

import joblib
import numpy as np
import pandas as pd
from lime.lime_tabular import LimeTabularExplainer


# --------------------------------------------------
# Configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_ROOT = PROJECT_ROOT / "model"

MODEL_PATH = MODEL_ROOT / "sensor_random_forest_pipeline.joblib"
METADATA_PATH = MODEL_ROOT / "sensor_model_metadata.json"


FEATURES = ["HR", "O2Sat", "Temp"]
TARGET = "SepsisLabel"
# DATASET_PATH = PROJECT_ROOT / "combined_sepsis_data.csv"
MIN_LIME_FIT_SCORE = 0.5
_explanation_lock = Lock()


# --------------------------------------------------
# Load model artifacts
# --------------------------------------------------

def load_artifacts():
    for path in (
        
        MODEL_PATH,
        METADATA_PATH,
    ):
        if not path.is_file():
            raise FileNotFoundError(
                f"Required project file not found: {path}"
            )

    with METADATA_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    if metadata.get("features") != FEATURES:
        raise ValueError(
            f"Expected model features {FEATURES}; "
            f"found {metadata.get('features')}"
        )

    threshold = float(
        metadata.get("selected_threshold", float("nan"))
    )

    if (
        not np.isfinite(threshold)
        or not 0 <= threshold <= 1
    ):
        raise ValueError(
            "The selected threshold must be between 0 and 1."
        )

    model = joblib.load(MODEL_PATH)

    model_features = getattr(
        model,
        "feature_names_in_",
        None,
    )

    if (
        model_features is not None
        and list(model_features) != FEATURES
    ):
        raise ValueError(
            "Saved model feature order is incorrect: "
            f"{list(model_features)}"
        )

    classes = getattr(model, "classes_", None)

    if classes is not None:
        if not np.array_equal(
            np.asarray(classes),
            np.array([0, 1]),
        ):
            raise ValueError(
                f"Expected model classes [0, 1], got {classes}."
            )

    if not hasattr(model, "predict_proba"):
        raise TypeError(
            "Saved model does not provide predict_proba()."
        )

    return model, metadata


# --------------------------------------------------
# Prepare LIME reference data
# --------------------------------------------------

def load_reference_data():
    df = pd.read_csv(DATASET_PATH)

    required_columns = FEATURES + [TARGET]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Dataset is missing columns: {missing}"
        )

    X = df[FEATURES].apply(
        pd.to_numeric,
        errors="coerce",
    )

    X = X.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    X = X.dropna(
        subset=FEATURES,
    ).reset_index(drop=True)

    if X.empty:
        raise ValueError(
            "No complete sensor rows are available for LIME."
        )

    return X


# --------------------------------------------------
# Initialize model and LIME once
# --------------------------------------------------

model, metadata = load_artifacts()

if DATASET_PATH.is_file():
    reference_data = load_reference_data()

    explainer = LimeTabularExplainer(
        training_data=reference_data[FEATURES].to_numpy(
            dtype=float
        ),
        feature_names=FEATURES,
        class_names=[
            "No sepsis risk flag",
            "Sepsis risk flag",
        ],
        mode="classification",
        discretize_continuous=True,
        random_state=42,
    )
else:
    reference_data = None
    explainer = None

# --------------------------------------------------
# Prediction adapter for LIME
# --------------------------------------------------

def predict_probabilities(rows):
    """
    Return probabilities in [non-flag, risk-flag] order.
    Accept either a list or a NumPy array from LIME.
    """

    rows = np.asarray(rows, dtype=float)

    if rows.ndim == 1:
        rows = rows.reshape(1, -1)

    if rows.ndim != 2 or rows.shape[1] != len(FEATURES):
        raise ValueError(
            "Expected exactly three sensor features."
        )

    if not np.isfinite(rows).all():
        raise ValueError(
            "LIME inputs must contain finite numbers."
        )

    frame = pd.DataFrame(
        rows,
        columns=FEATURES,
    )

    probabilities = model.predict_proba(frame)

    probabilities = np.asarray(
        probabilities,
        dtype=float,
    )

    if (
        probabilities.ndim != 2
        or probabilities.shape[1] != 2
    ):
        raise ValueError(
            "The model must return two class probabilities."
        )

    return probabilities


# --------------------------------------------------
# Explain one incoming sensor reading
# --------------------------------------------------

def explain_reading(
    bpm,
    temperature,
    spo2,
    num_features=3,
):
    """
    Generate a local LIME explanation.

    API input order: bpm, temperature, spo2.
    Model feature order: HR, O2Sat, Temp.
    """
    
    if explainer is None:
        raise RuntimeError(
            "LIME explanation is unavailable because the "
            "training reference dataset is not deployed."
        )
    
    if explainer is None:
        raise RuntimeError(
            "LIME explanation is unavailable because the "
            "training reference dataset is not deployed."
        )

    values = {
        "HR": float(bpm),
        "O2Sat": float(spo2),
        "Temp": float(temperature),
    }

    if not all(
        np.isfinite(value)
        for value in values.values()
    ):
        raise ValueError(
            "Sensor readings must be finite numbers."
        )

    # Preserve the exact feature order used during training.
    sample_values = np.asarray(
        [values[name] for name in FEATURES],
        dtype=float,
    )

    if sample_values.shape != (len(FEATURES),):
        raise ValueError(
            "The sensor sample has an incorrect shape."
        )

    # Use a DataFrame for the saved model's feature names.
    sample_frame = pd.DataFrame(
        [sample_values],
        columns=FEATURES,
    )

    probabilities = predict_probabilities(
        sample_frame.to_numpy(dtype=float)
    )[0]

    predicted_probability = float(probabilities[1])

    threshold = float(
        metadata["selected_threshold"]
    )

    # Generate LIME's local explanation reproducibly.
    with _explanation_lock:
        explainer.random_state.seed(42)

        explanation = explainer.explain_instance(
            data_row=sample_values,
            predict_fn=predict_probabilities,
            labels=(1,),
            num_features=min(
                max(int(num_features), 1),
                len(FEATURES),
            ),
            num_samples=5000,
        )

    fit_score = float(explanation.score)

    fit_is_finite = bool(
        np.isfinite(fit_score)
    )

    reliable = (
        fit_is_finite
        and fit_score >= MIN_LIME_FIT_SCORE
    )

    # Return contributions even when the local fit is low.
    feature_effects = []

    for feature, weight in explanation.as_list(label=1):
        weight = float(weight)

        if weight > 0:
            effect = "supports risk flag"
        elif weight < 0:
            effect = "opposes risk flag"
        else:
            effect = "neutral"

        feature_effects.append({
            "feature_rule": feature,
            "weight": weight,
            "effect": effect,
        })

    if not feature_effects:
        explanation_status = "unavailable"

        explanation_message = (
            "LIME did not return feature contributions."
        )

    elif not reliable:
        explanation_status = "low_fit"

        explanation_message = (
            "LIME contributions are displayed, but the local "
            "fit score is low. Interpret them cautiously; "
            "they are not clinical evidence."
        )

    else:
        explanation_status = "available"

        explanation_message = (
            "LIME contributions are displayed. The local fit "
            "score is a diagnostic and does not establish "
            "clinical validity."
        )

    return {
        "prediction": (
            "SEPSIS_RISK_FLAG"
            if predicted_probability >= threshold
            else "NO_RISK_FLAG"
        ),
        "sepsis_probability": predicted_probability,
        "threshold": threshold,
        "features": values,
        "explanation": feature_effects,
        "explanation_status": explanation_status,
        "local_fit_score": (
            fit_score if fit_is_finite else None
        ),
        "explanation_message": explanation_message,
        "warning": (
            "Experimental model output. This is not a diagnosis "
            "or a clinically validated risk estimate. A "
            "NO_RISK_FLAG does not establish that a person "
            "is healthy."
        ),
    }
