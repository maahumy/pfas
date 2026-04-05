"""
09_predict_risk.py

Score the untested-systems pool with the trained model. Categorize into
Low / Moderate / High / Very High risk bins and print the top candidates.

Inputs:
  data/cleaned/model_prediction_targets.csv
  data/cleaned/best_model.joblib (+ optional scaler.joblib)
Output:
  data/cleaned/predicted_risk_scores.csv

Run from pfas-risk-ma/:
  python scripts/09_predict_risk.py
"""

from pathlib import Path
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "cleaned"

FEATURE_COLS = [
    "dist_airport_km", "dist_military_km", "dist_landfill_km",
    "dist_wwtp_km", "dist_industrial_km",
    "is_groundwater",
    "landfills_within_5km", "industrial_within_5km",
]


def main():
    df = pd.read_csv(CLEAN / "model_prediction_targets.csv", dtype={"PWSID": str})
    model = joblib.load(CLEAN / "best_model.joblib")

    scaler_path = CLEAN / "scaler.joblib"
    scaler = joblib.load(scaler_path) if scaler_path.exists() else None

    X = df[FEATURE_COLS].values
    if scaler is not None:
        X = scaler.transform(X)
    probs = model.predict_proba(X)[:, 1]
    df["predicted_risk_score"] = probs
    df["risk_category"] = pd.cut(
        probs, bins=[-0.001, 0.25, 0.50, 0.75, 1.001],
        labels=["Low", "Moderate", "High", "Very High"],
    )

    print(f"Scored {len(df)} untested systems")
    print("\nRisk category distribution:")
    print(df["risk_category"].value_counts().sort_index().to_string())

    print("\n=== Top 20 highest-risk untested systems ===")
    cols = ["PWSID", "SITE_NAME", "TOWN", "predicted_risk_score", "risk_category",
            "dist_airport_km", "dist_military_km", "dist_landfill_km",
            "dist_industrial_km", "serves_ej_community"]
    cols = [c for c in cols if c in df.columns]
    print(df.nlargest(20, "predicted_risk_score")[cols].round(3).to_string(index=False))

    df.to_csv(CLEAN / "predicted_risk_scores.csv", index=False)
    print(f"\nWrote predicted_risk_scores.csv ({len(df)} rows)")


if __name__ == "__main__":
    main()
