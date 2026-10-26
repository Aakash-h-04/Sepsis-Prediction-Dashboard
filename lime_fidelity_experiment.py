
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lime.lime_tabular import LimeTabularExplainer


# ============================================================
# LIME FIDELITY EXPERIMENT
# Uses the existing sensor-only model.
# Does not modify the model or dashboard.
# ============================================================

ML_ROOT = Path(
    r"C:\Users\prate\Downloads\Early_Sepsis_Prediction"
)

DATA_PATH = ML_ROOT / "combined_sepsis_data.csv"
MODEL_PATH = (
    ML_ROOT / "module2_ml" / "sensor_random_forest_pipeline.joblib"
)
METADATA_PATH = (
    ML_ROOT / "module2_ml" / "sensor_model_metadata.json"
)

FEATURES = ["HR", "O2Sat", "Temp"]

SAMPLE = np.array([82.0, 95.0, 36.5])

NUM_SAMPLES = 5000
RANDOM_SEED = 42


def main():
    # --------------------------------------------------------
    # 1. Verify required files
    # --------------------------------------------------------

    print("=" * 65)
    print("LIME FIDELITY EXPERIMENT")
    print("=" * 65)

    for path in (DATA_PATH, MODEL_PATH, METADATA_PATH):
        print(f"Checking: {path}")

        if not path.is_file():
            raise FileNotFoundError(
                f"Required project file not found:\n{path}"
            )

    # --------------------------------------------------------
    # 2. Load the existing model and metadata
    # --------------------------------------------------------

    print("\nLoading saved model...")

    model = joblib.load(MODEL_PATH)

    with METADATA_PATH.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    if metadata.get("features") != FEATURES:
        raise ValueError(
            "Metadata feature order does not match "
            f"the expected order: {FEATURES}"
        )

    if list(model.feature_names_in_) != FEATURES:
        raise ValueError(
            "Saved model feature order does not match "
            f"the expected order: {FEATURES}"
        )

    print("Model loaded successfully.")
    print("Features:", FEATURES)

    # --------------------------------------------------------
    # 3. Prepare LIME reference data
    # --------------------------------------------------------

    print("\nLoading reference dataset...")

    df = pd.read_csv(DATA_PATH)

    reference = df[FEATURES].apply(
        pd.to_numeric,
        errors="raise"
    )

    reference = reference.replace(
        [np.inf, -np.inf],
        np.nan
    )

    reference = reference.dropna().reset_index(drop=True)

    if len(reference) < 100:
        raise ValueError(
            "Fewer than 100 complete reference rows are available."
        )

    print("Dataset rows:", len(df))
    print("Complete reference rows:", len(reference))

    # --------------------------------------------------------
    # 4. Create the prediction adapter
    # --------------------------------------------------------

    def predict_proba(rows):
        rows = np.asarray(rows, dtype=float)

        if rows.ndim == 1:
            rows = rows.reshape(1, -1)

        if rows.ndim != 2 or rows.shape[1] != len(FEATURES):
            raise ValueError(
                "Expected input rows containing exactly three features."
            )

        if not np.isfinite(rows).all():
            raise ValueError(
                "Prediction input contains non-finite values."
            )

        frame = pd.DataFrame(
            rows,
            columns=FEATURES
        )

        return model.predict_proba(frame)

    # --------------------------------------------------------
    # 5. Establish the actual model prediction
    # --------------------------------------------------------

    actual_probability = float(
        predict_proba(SAMPLE)[0, 1]
    )

    threshold = float(metadata["selected_threshold"])

    print("\n" + "-" * 65)
    print("TEST INPUT")
    print("-" * 65)
    print(f"HR:                   {SAMPLE[0]}")
    print(f"SpO2:                 {SAMPLE[1]}")
    print(f"Temperature:          {SAMPLE[2]}")
    print(f"Model probability:    {actual_probability:.6f}")
    print(f"Selected threshold:   {threshold:.6f}")
    print(
        "Model output:         "
        + (
            "SEPSIS_RISK_FLAG"
            if actual_probability >= threshold
            else "NO_RISK_FLAG"
        )
    )

    # --------------------------------------------------------
    # 6. Compare LIME configurations
    # --------------------------------------------------------

    configurations = [
        (True, 0.50),
        (True, 0.75),
        (True, 1.30),
        (True, 2.00),
        (False, 0.50),
        (False, 0.75),
        (False, 1.30),
        (False, 2.00),
    ]

    results = []

    print("\nTesting LIME configurations...")
    print(f"Samples per configuration: {NUM_SAMPLES}")

    for number, (discretize, kernel_width) in enumerate(
        configurations,
        start=1
    ):
        print(
            f"\nConfiguration {number}/{len(configurations)}: "
            f"discretize={discretize}, "
            f"kernel_width={kernel_width}"
        )

        explainer = LimeTabularExplainer(
            training_data=reference[FEATURES].to_numpy(dtype=float),
            feature_names=FEATURES,
            class_names=[
                "No sepsis risk flag",
                "Sepsis risk flag"
            ],
            mode="classification",
            discretize_continuous=discretize,
            kernel_width=kernel_width,
            random_state=RANDOM_SEED,
        )

        explanation = explainer.explain_instance(
            data_row=SAMPLE.copy(),
            predict_fn=predict_proba,
            labels=(1,),
            num_features=len(FEATURES),
            num_samples=NUM_SAMPLES,
        )

        local_fit = float(explanation.score)
        local_prediction = float(
            np.ravel(explanation.local_pred)[0]
        )
        probability_gap = abs(
            actual_probability - local_prediction
        )

        result = {
            "discretize_continuous": discretize,
            "kernel_width": kernel_width,
            "local_fit_score": local_fit,
            "model_probability": actual_probability,
            "lime_local_prediction": local_prediction,
            "absolute_probability_gap": probability_gap,
        }

        results.append(result)

        print(f"  Local fit score:          {local_fit:.6f}")
        print(f"  Model probability:        {actual_probability:.6f}")
        print(f"  LIME local prediction:    {local_prediction:.6f}")
        print(f"  Absolute probability gap: {probability_gap:.6f}")

        print("  Feature contributions:")
        for feature, weight in explanation.as_list(label=1):
            print(f"    {feature}: {weight:+.6f}")

    # --------------------------------------------------------
    # 7. Rank and save results
    # --------------------------------------------------------

    results.sort(
        key=lambda item: (
            -item["local_fit_score"],
            item["absolute_probability_gap"],
        )
    )

    print("\n" + "=" * 65)
    print("CONFIGURATION COMPARISON")
    print("=" * 65)

    for rank, result in enumerate(results, start=1):
        print(
            f"{rank}. discretize="
            f"{result['discretize_continuous']}, "
            f"kernel_width={result['kernel_width']:.2f}, "
            f"fit={result['local_fit_score']:.6f}, "
            f"gap={result['absolute_probability_gap']:.6f}"
        )

    output_path = ML_ROOT / "lime_fidelity_results.csv"

    pd.DataFrame(results).to_csv(
        output_path,
        index=False
    )

    print("\nResults saved to:")
    print(output_path)

    print("\nExperiment finished.")
    print("The saved model and dashboard files were not modified.")
    print(
        "Note: LIME fit scores measure local approximation, "
        "not clinical validity."
    )


if __name__ == "__main__":
    main()
