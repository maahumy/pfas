"""
08_train_model.py

Train Logistic Regression + Random Forest binary classifiers for PFAS detection
based on distance features. Evaluate with stratified 80/20 test split and 5-fold
cross-validated ROC AUC. Save confusion matrices, ROC curves, and feature
importance plots. Select and persist the better model.

Input:  data/cleaned/model_training_data.csv
Outputs:
  data/cleaned/best_model.joblib, scaler.joblib (if LR selected)
  maps/model_evaluation.png, maps/feature_importance.png

Run from pfas-risk-ma/:
  python scripts/08_train_model.py
"""

from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (classification_report, roc_auc_score,
                             ConfusionMatrixDisplay, RocCurveDisplay)

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "cleaned"
MAPS = ROOT / "maps"

FEATURE_COLS = [
    "dist_airport_km", "dist_military_km", "dist_landfill_km",
    "dist_wwtp_km", "dist_industrial_km",
    "is_groundwater",
    "landfills_within_5km", "industrial_within_5km",
]
TARGET_COL = "pfas_detected"
RNG = 42


def main():
    df = pd.read_csv(CLEAN / "model_training_data.csv")
    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].astype(int).values

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=RNG, stratify=y
    )
    print(f"Train: {len(X_tr)} ({y_tr.sum()} positive)  "
          f"Test: {len(X_te)} ({y_te.sum()} positive)")

    # Logistic Regression (scaled)
    scaler = StandardScaler().fit(X_tr)
    X_tr_s, X_te_s = scaler.transform(X_tr), scaler.transform(X_te)
    lr = LogisticRegression(class_weight="balanced", random_state=RNG, max_iter=2000)
    lr.fit(X_tr_s, y_tr)
    y_prob_lr = lr.predict_proba(X_te_s)[:, 1]
    y_pred_lr = lr.predict(X_te_s)

    print("\n===== LOGISTIC REGRESSION =====")
    print(classification_report(y_te, y_pred_lr, target_names=["No PFAS", "PFAS"]))
    auc_lr = roc_auc_score(y_te, y_prob_lr)
    print(f"Test ROC AUC: {auc_lr:.3f}")
    cv_lr = cross_val_score(lr, scaler.transform(X_tr), y_tr, cv=5, scoring="roc_auc")
    print(f"5-fold CV AUC: {cv_lr.mean():.3f} (+/- {cv_lr.std():.3f})")
    print("Coefficients (log-odds, scaled features):")
    for f, c in sorted(zip(FEATURE_COLS, lr.coef_[0]), key=lambda x: abs(x[1]), reverse=True):
        print(f"  {'+' if c > 0 else '-'} {f}: {c:+.4f}")

    # Random Forest
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=5, class_weight="balanced", random_state=RNG
    )
    rf.fit(X_tr, y_tr)
    y_prob_rf = rf.predict_proba(X_te)[:, 1]
    y_pred_rf = rf.predict(X_te)

    print("\n===== RANDOM FOREST =====")
    print(classification_report(y_te, y_pred_rf, target_names=["No PFAS", "PFAS"]))
    auc_rf = roc_auc_score(y_te, y_prob_rf)
    print(f"Test ROC AUC: {auc_rf:.3f}")
    cv_rf = cross_val_score(rf, X_tr, y_tr, cv=5, scoring="roc_auc")
    print(f"5-fold CV AUC: {cv_rf.mean():.3f} (+/- {cv_rf.std():.3f})")
    print("Feature importance (Gini):")
    for f, imp in sorted(zip(FEATURE_COLS, rf.feature_importances_),
                         key=lambda x: x[1], reverse=True):
        print(f"  {f}: {imp:.4f}")

    # Combined diagnostic figure
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    ConfusionMatrixDisplay.from_predictions(
        y_te, y_pred_lr, display_labels=["No PFAS", "PFAS"], ax=axes[0], cmap="Blues"
    )
    axes[0].set_title(f"Logistic Regression (AUC={auc_lr:.3f})")
    ConfusionMatrixDisplay.from_predictions(
        y_te, y_pred_rf, display_labels=["No PFAS", "PFAS"], ax=axes[1], cmap="Greens"
    )
    axes[1].set_title(f"Random Forest (AUC={auc_rf:.3f})")
    RocCurveDisplay.from_predictions(y_te, y_prob_lr, ax=axes[2], name="Logistic Reg.")
    RocCurveDisplay.from_predictions(y_te, y_prob_rf, ax=axes[2], name="Random Forest")
    axes[2].plot([0, 1], [0, 1], "k--", label="Random (AUC=0.5)")
    axes[2].set_title("ROC Curves")
    axes[2].legend()
    plt.tight_layout()
    plt.savefig(MAPS / "model_evaluation.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Feature importance comparison
    fig, ax = plt.subplots(figsize=(9, 5))
    x_pos = np.arange(len(FEATURE_COLS))
    width = 0.38
    lr_imp_norm = np.abs(lr.coef_[0]) / np.abs(lr.coef_[0]).max()
    ax.barh(x_pos - width/2, lr_imp_norm, width, label="Logistic Reg. (|coef|, normalized)")
    ax.barh(x_pos + width/2, rf.feature_importances_, width, label="Random Forest (Gini)")
    ax.set_yticks(x_pos)
    ax.set_yticklabels(FEATURE_COLS)
    ax.set_xlabel("Relative Importance")
    ax.set_title("Feature Importance Comparison")
    ax.legend(loc="lower right")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(MAPS / "feature_importance.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Select best model (prefer LR for interpretability unless RF much better)
    if auc_lr >= auc_rf - 0.02:
        best, name, use_scaler = lr, "Logistic Regression", True
    else:
        best, name, use_scaler = rf, "Random Forest", False
    print(f"\nSelected: {name}")

    joblib.dump(best, CLEAN / "best_model.joblib")
    if use_scaler:
        joblib.dump(scaler, CLEAN / "scaler.joblib")
    else:
        sc_path = CLEAN / "scaler.joblib"
        if sc_path.exists():
            sc_path.unlink()
    # Persist metadata
    meta = {"model": name, "use_scaler": use_scaler, "auc_lr": auc_lr, "auc_rf": auc_rf,
            "features": FEATURE_COLS}
    (CLEAN / "model_meta.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in meta.items()), encoding="utf-8"
    )
    print(f"Saved: best_model.joblib, model_meta.txt; plots in maps/")


if __name__ == "__main__":
    main()
