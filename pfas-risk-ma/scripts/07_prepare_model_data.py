"""
07_prepare_model_data.py

Split the feature-engineered dataset into training pool (UCMR5-tested) and
prediction pool (untested). Handle NaNs, coerce booleans to int, print class
balance.

Input:  data/cleaned/pws_features_final.csv
Outputs:
  data/cleaned/model_training_data.csv
  data/cleaned/model_prediction_targets.csv

Run from pfas-risk-ma/:
  python scripts/07_prepare_model_data.py
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "cleaned"

FEATURE_COLS = [
    "dist_airport_km", "dist_military_km", "dist_landfill_km",
    "dist_wwtp_km", "dist_industrial_km",
    "is_groundwater",
    "landfills_within_5km", "industrial_within_5km",
]
TARGET_COL = "pfas_detected"


def main():
    df = pd.read_csv(CLEAN / "pws_features_final.csv", dtype={"PWSID": str})
    print(f"Total PWSs: {len(df)}")
    print(f"In UCMR5: {df['in_ucmr5'].sum()}  |  Not in UCMR5: {(~df['in_ucmr5']).sum()}")

    # Coerce booleans to int
    for col in ("is_groundwater", "is_mwra", "serves_ej_community",
                "any_income", "any_minority", "any_english"):
        if col in df.columns:
            df[col] = df[col].astype(bool).astype(int)

    train = df[df["in_ucmr5"]].copy()
    predict = df[~df["in_ucmr5"]].copy()

    # Drop rows with NaN in features
    n_before = len(train)
    train = train.dropna(subset=FEATURE_COLS + [TARGET_COL])
    print(f"Training rows: {len(train)} (dropped {n_before - len(train)} NaN)")

    train[TARGET_COL] = train[TARGET_COL].astype(int)

    print(f"\n=== Class balance (training pool) ===")
    pos = train[TARGET_COL].sum()
    neg = len(train) - pos
    print(f"  PFAS detected:     {pos}  ({pos/len(train):.1%})")
    print(f"  No detection:      {neg}  ({neg/len(train):.1%})")
    if max(pos, neg) / len(train) > 0.8:
        print("  !!! SEVERE IMBALANCE (>80/20) — will use class_weight='balanced'")

    # MWRA breakdown
    print(f"\n=== MWRA systems in training pool ===")
    print(f"  MWRA:     {train['is_mwra'].sum()}")
    print(f"  Non-MWRA: {(~train['is_mwra'].astype(bool)).sum()}")

    # Prediction pool: keep those with valid features only
    n_pred = len(predict)
    predict = predict.dropna(subset=FEATURE_COLS)
    print(f"\nPrediction targets with complete features: {len(predict)} "
          f"(dropped {n_pred - len(predict)} with missing features)")

    train.to_csv(CLEAN / "model_training_data.csv", index=False)
    predict.to_csv(CLEAN / "model_prediction_targets.csv", index=False)
    print(f"\nWrote model_training_data.csv ({len(train)} rows)")
    print(f"Wrote model_prediction_targets.csv ({len(predict)} rows)")


if __name__ == "__main__":
    main()
