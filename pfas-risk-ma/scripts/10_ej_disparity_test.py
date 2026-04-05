"""
10_ej_disparity_test.py

Statistical tests: are high-risk UNTESTED water systems disproportionately
located in EJ communities?

Tests:
  1. Chi-square on 2x2 high-risk x EJ contingency table
  2. One-sided Mann-Whitney U (risk score, EJ > non-EJ)
  3. Proportion of high-risk systems in EJ vs. non-EJ

Input: data/cleaned/predicted_risk_scores.csv
Output: data/cleaned/ej_disparity_results.txt

Run from pfas-risk-ma/:
  python scripts/10_ej_disparity_test.py
"""

from pathlib import Path
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "cleaned"
THRESHOLD = 0.5


def main():
    df = pd.read_csv(CLEAN / "predicted_risk_scores.csv")
    df = df.dropna(subset=["predicted_risk_score", "serves_ej_community"])
    df["serves_ej_community"] = df["serves_ej_community"].astype(bool)
    df["high_risk"] = df["predicted_risk_score"] > THRESHOLD

    lines = []

    def log(s):
        print(s)
        lines.append(s)

    log("EJ DISPARITY ANALYSIS — UNTESTED MASSACHUSETTS PWS")
    log("=" * 56)
    log(f"Risk score threshold for 'high risk': > {THRESHOLD}")
    log(f"N = {len(df)} untested systems with valid EJ and risk values")
    log("")

    # Contingency table
    ct = pd.crosstab(
        df["high_risk"].map({True: "High Risk", False: "Lower Risk"}),
        df["serves_ej_community"].map({True: "EJ Community", False: "Non-EJ"}),
    )
    log("Contingency table:")
    log(ct.to_string())
    log("")

    chi2, p_chi2, dof, _ = stats.chi2_contingency(ct)
    log(f"Chi-square: chi2 = {chi2:.2f}, dof = {dof}, p = {p_chi2:.4f}")
    log(("  STATISTICALLY SIGNIFICANT (alpha=0.05): high-risk systems are "
         "disproportionately in EJ communities.")
        if p_chi2 < 0.05 else
        "  NOT statistically significant at alpha=0.05.")
    log("")

    # Mann-Whitney U (one-sided, EJ > non-EJ)
    ej_scores = df.loc[df["serves_ej_community"], "predicted_risk_score"]
    non_ej_scores = df.loc[~df["serves_ej_community"], "predicted_risk_score"]
    u_stat, p_mw = stats.mannwhitneyu(ej_scores, non_ej_scores, alternative="greater")
    log(f"Mann-Whitney U (one-sided, EJ > non-EJ): U = {u_stat:.0f}, p = {p_mw:.4f}")
    log(f"  EJ:     mean = {ej_scores.mean():.3f}, median = {ej_scores.median():.3f}, n = {len(ej_scores)}")
    log(f"  Non-EJ: mean = {non_ej_scores.mean():.3f}, median = {non_ej_scores.median():.3f}, n = {len(non_ej_scores)}")
    log("")

    pct_hr_ej = (ej_scores > THRESHOLD).mean()
    pct_hr_non_ej = (non_ej_scores > THRESHOLD).mean()
    log("Proportion classified as high risk:")
    log(f"  EJ communities:     {pct_hr_ej:.1%}")
    log(f"  Non-EJ communities: {pct_hr_non_ej:.1%}")
    log(f"  Ratio (EJ / Non-EJ): {pct_hr_ej / pct_hr_non_ej:.2f}" if pct_hr_non_ej > 0 else "")

    (CLEAN / "ej_disparity_results.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote ej_disparity_results.txt")


if __name__ == "__main__":
    main()
