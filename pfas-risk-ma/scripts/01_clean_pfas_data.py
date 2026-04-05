"""
01_clean_pfas_data.py

Clean the UCMR5 Massachusetts PFAS data:
  - Handle non-detects (substitute half the MRL, standard practice)
  - Convert µg/L -> ng/L (ppt) since MA MMCL and federal MCL are in ppt
  - Flag detections that exceed the federal MCL (PFOA/PFOS > 4 ppt)
  - Compute PFAS6 sum per sample event and flag MA MMCL exceedances (> 20 ppt)
  - Produce a per-PWS summary table for mapping

Inputs:
  data/raw/ucmr5_ma_pfas.csv

Outputs:
  data/cleaned/ucmr5_ma_all_results.csv        (all individual results, cleaned)
  data/cleaned/ucmr5_ma_pfas6_sums.csv         (PFAS6 sum per PWS per sample date)
  data/cleaned/ucmr5_ma_system_summary.csv     (one row per PWS, summary stats)

Run from the pfas-risk-ma/ directory:
  python scripts/01_clean_pfas_data.py
"""

from pathlib import Path
import pandas as pd

# Project paths
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "cleaned"
CLEAN.mkdir(parents=True, exist_ok=True)

# Federal MCL (EPA, finalized 2024): PFOA and PFOS each at 4.0 ng/L (ppt)
FEDERAL_MCL_PPT = 4.0

# Massachusetts MMCL: PFAS6 sum <= 20 ng/L (ppt)
# PFAS6 = PFOA, PFOS, PFHxS, PFNA, PFHpA, PFDA
PFAS6 = ["PFOA", "PFOS", "PFHxS", "PFNA", "PFHpA", "PFDA"]
MA_MMCL_PFAS6_PPT = 20.0


def load_ucmr5():
    """Load the MA-filtered UCMR5 file and print sanity checks."""
    path = RAW / "ucmr5_ma_pfas.csv"
    df = pd.read_csv(path, dtype={"PWSID": str})
    print(f"Loaded {path}")
    print(f"  columns: {df.columns.tolist()}")
    print(f"  total records:        {len(df):,}")
    print(f"  unique PWSs:          {df['PWSID'].nunique()}")
    print(f"  unique contaminants:  {df['Contaminant'].nunique()}")
    print(f"  detections (sign ='='): {(df['AnalyticalResultsSign'] == '=').sum():,}")
    print(f"  non-detects (sign '<'): {(df['AnalyticalResultsSign'] == '<').sum():,}")
    print("  contaminant counts:")
    print(df["Contaminant"].value_counts().to_string())
    print()
    return df


def clean_results(df: pd.DataFrame) -> pd.DataFrame:
    """Add concentration_ppt, detected, and MCL-exceedance columns."""
    # Non-detects: concentration is below MRL. Substitute MRL/2 (standard practice).
    sign = df["AnalyticalResultsSign"].astype(str).str.strip()
    detected = sign == "="

    # UCMR5 reports in µg/L. Some releases omit the result value for non-detects.
    result_ugL = pd.to_numeric(df["AnalyticalResultValue"], errors="coerce")
    mrl_ugL = pd.to_numeric(df["MRL"], errors="coerce")
    conc_ugL = result_ugL.where(detected, mrl_ugL / 2.0)

    df = df.copy()
    df["detected"] = detected
    df["concentration_ugL"] = conc_ugL
    df["concentration_ppt"] = conc_ugL * 1000.0  # 1 µg/L = 1000 ng/L = 1000 ppt
    df["pfas_abbrev"] = df["Contaminant"].str.strip()

    # Federal MCL flag applies only to PFOA/PFOS detections above 4 ppt
    df["exceeds_federal_mcl"] = (
        df["pfas_abbrev"].isin(["PFOA", "PFOS"])
        & df["detected"]
        & (df["concentration_ppt"] > FEDERAL_MCL_PPT)
    )
    return df


def pfas6_sum_per_event(df: pd.DataFrame) -> pd.DataFrame:
    """Compute PFAS6 sum per (PWSID, CollectionDate, SamplePointID) event."""
    pf6 = df[df["pfas_abbrev"].isin(PFAS6)].copy()
    group_cols = ["PWSID", "PWSName", "SamplePointID", "CollectionDate"]
    agg = (
        pf6.groupby(group_cols, as_index=False)
        .agg(
            pfas6_sum_ppt=("concentration_ppt", "sum"),
            pfas6_n_detected=("detected", "sum"),
            pfas6_n_analytes=("pfas_abbrev", "nunique"),
        )
    )
    agg["exceeds_ma_mmcl"] = agg["pfas6_sum_ppt"] > MA_MMCL_PFAS6_PPT
    return agg


def system_summary(df: pd.DataFrame, pfas6_sums: pd.DataFrame) -> pd.DataFrame:
    """One row per public water system with summary statistics."""
    # Per-compound max per PWS (detections only)
    det = df[df["detected"]]
    pfoa_max = det[det["pfas_abbrev"] == "PFOA"].groupby("PWSID")["concentration_ppt"].max()
    pfos_max = det[det["pfas_abbrev"] == "PFOS"].groupby("PWSID")["concentration_ppt"].max()

    # Count of distinct PFAS compounds detected at each PWS
    n_detected = (
        det.groupby("PWSID")["pfas_abbrev"].nunique().rename("num_pfas_detected")
    )

    # Max PFAS6 sum per PWS, and did any sample ever exceed MA MMCL?
    pf6_max = (
        pfas6_sums.groupby("PWSID")
        .agg(
            max_pfas6_sum_ppt=("pfas6_sum_ppt", "max"),
            ever_exceeded_ma_mmcl=("exceeds_ma_mmcl", "any"),
        )
    )

    base = df.groupby("PWSID").agg(
        pws_name=("PWSName", "first"),
        total_samples=("SampleID", "nunique"),
        total_results=("concentration_ppt", "count"),
        any_detection=("detected", "any"),
        ever_exceeded_federal_mcl=("exceeds_federal_mcl", "any"),
    )

    out = base.join([pfoa_max.rename("max_pfoa_ppt"), pfos_max.rename("max_pfos_ppt"),
                     n_detected, pf6_max]).reset_index()
    # Fill counts/flags for PWSs with no detections
    out["num_pfas_detected"] = out["num_pfas_detected"].fillna(0).astype(int)
    for col in ["ever_exceeded_ma_mmcl", "ever_exceeded_federal_mcl"]:
        out[col] = out[col].fillna(False).astype(bool)
    return out


def main():
    df = load_ucmr5()
    cleaned = clean_results(df)
    pf6 = pfas6_sum_per_event(cleaned)
    summary = system_summary(cleaned, pf6)

    # Save outputs
    all_out = CLEAN / "ucmr5_ma_all_results.csv"
    pf6_out = CLEAN / "ucmr5_ma_pfas6_sums.csv"
    sum_out = CLEAN / "ucmr5_ma_system_summary.csv"
    cleaned.to_csv(all_out, index=False)
    pf6.to_csv(pf6_out, index=False)
    summary.to_csv(sum_out, index=False)

    print("=== Summary ===")
    print(f"  federal MCL exceedances (PFOA/PFOS > {FEDERAL_MCL_PPT} ppt): "
          f"{cleaned['exceeds_federal_mcl'].sum():,}")
    print(f"  PWSs with any detection: {summary['any_detection'].sum()} / {len(summary)}")
    print(f"  PWSs ever exceeding federal MCL: "
          f"{summary['ever_exceeded_federal_mcl'].sum()}")
    print(f"  PWSs ever exceeding MA MMCL (PFAS6 > {MA_MMCL_PFAS6_PPT} ppt): "
          f"{summary['ever_exceeded_ma_mmcl'].sum()}")
    print()
    print(f"Wrote {all_out}  ({len(cleaned):,} rows)")
    print(f"Wrote {pf6_out}  ({len(pf6):,} rows)")
    print(f"Wrote {sum_out}  ({len(summary):,} rows)")


if __name__ == "__main__":
    main()
