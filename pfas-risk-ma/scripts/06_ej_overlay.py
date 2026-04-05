"""
06_ej_overlay.py

For each PWS service area polygon, compute the area-fraction overlap with EJ
block groups. Merge back onto the PWS feature dataset.

Inputs (data/cleaned/):
  pws_service_areas.gpkg, ej_populations.gpkg, pws_features_engineered.gpkg

Output:
  data/cleaned/pws_features_final.gpkg + .csv

Run from pfas-risk-ma/:
  python scripts/06_ej_overlay.py
"""

from pathlib import Path
import warnings
import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore", message=".*CRS.*")

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "cleaned"


def main():
    service = gpd.read_file(CLEAN / "pws_service_areas.gpkg")
    ej = gpd.read_file(CLEAN / "ej_populations.gpkg")
    features = gpd.read_file(CLEAN / "pws_features_engineered.gpkg")

    print(f"PWS service areas: {len(service)}")
    print(f"EJ block groups: {len(ej)}")
    print(f"Service area cols: {service.columns.tolist()[:10]}...")

    # Filter EJ block groups flagged as EJ (EJ = 'Yes')
    ej_only = ej[ej["EJ"] == "Yes"].copy()
    print(f"Block groups flagged as EJ: {len(ej_only)}")
    print(f"EJ criteria distribution:\n{ej_only['EJ_CRITERI'].value_counts().to_string()}")

    # Keep essential columns on service areas
    service["PWSID"] = "MA" + service["PWS_ID"].astype(str).str.strip().str.zfill(7)
    service["total_area_m2"] = service.geometry.area

    # Dissolve EJ block groups per criterion into single multipolygon first to
    # avoid overlay explosion — but we also want to sum areas, so intersect
    # without dissolve is fine.
    svc_keep = service[["PWSID", "PWS_NAME", "total_area_m2", "geometry"]].rename(
        columns={"PWS_NAME": "service_name"}
    )
    ej_keep = ej_only[["GEOID", "EJ_CRITERI", "TOTAL_POP", "geometry"]]

    # Intersection — per service-area / per EJ-block-group slivers
    inter = gpd.overlay(svc_keep, ej_keep, how="intersection", keep_geom_type=True)
    inter["overlap_m2"] = inter.geometry.area
    print(f"Intersection slivers: {len(inter)}")

    # Helper flags per EJ criterion (I=Income, M=Minority, E=English, combos)
    def has_criterion(cc, letter):
        return cc.astype(str).str.contains(letter, case=False, na=False)

    inter["has_income"] = has_criterion(inter["EJ_CRITERI"], "I")
    inter["has_minority"] = has_criterion(inter["EJ_CRITERI"], "M")
    inter["has_english"] = has_criterion(inter["EJ_CRITERI"], "E")

    # Aggregate per PWSID
    agg = inter.groupby("PWSID", as_index=False).agg(
        ej_overlap_m2=("overlap_m2", "sum"),
        ej_population_overlapped=("TOTAL_POP", "sum"),
        any_income=("has_income", "any"),
        any_minority=("has_minority", "any"),
        any_english=("has_english", "any"),
        ej_criteria_distinct=("EJ_CRITERI", pd.Series.nunique),
    )

    # Merge back with service-area totals and compute fraction
    svc_lookup = svc_keep.drop(columns="geometry").drop_duplicates("PWSID")
    ej_summary = svc_lookup.merge(agg, on="PWSID", how="left")
    ej_summary["ej_overlap_m2"] = ej_summary["ej_overlap_m2"].fillna(0.0)
    ej_summary["ej_population_overlapped"] = ej_summary["ej_population_overlapped"].fillna(0.0)
    ej_summary["ej_area_fraction"] = (
        ej_summary["ej_overlap_m2"] / ej_summary["total_area_m2"]
    ).clip(0, 1)
    ej_summary["serves_ej_community"] = ej_summary["ej_area_fraction"] > 0
    for c in ("any_income", "any_minority", "any_english"):
        ej_summary[c] = ej_summary[c].fillna(False).astype(bool)
    ej_summary["ej_criteria_distinct"] = ej_summary["ej_criteria_distinct"].fillna(0).astype(int)

    print(f"\nPWS service areas summarized: {len(ej_summary)}")
    print(f"  serves_ej_community (any overlap): {ej_summary['serves_ej_community'].sum()}")
    print(f"  any_income criterion present: {ej_summary['any_income'].sum()}")
    print(f"  any_minority criterion present: {ej_summary['any_minority'].sum()}")
    print(f"  any_english criterion present: {ej_summary['any_english'].sum()}")

    # Merge EJ summary onto feature-engineered PWS dataset
    keep_cols = ["PWSID", "serves_ej_community", "ej_area_fraction",
                 "ej_population_overlapped", "any_income", "any_minority",
                 "any_english", "ej_criteria_distinct"]
    final = features.merge(ej_summary[keep_cols], on="PWSID", how="left")

    matched = final["serves_ej_community"].notna().sum()
    print(f"\nFeatures matched to a PWS service-area polygon: "
          f"{matched}/{len(final)}")

    # Fill NaN for PWSs with no service area polygon (transient systems without service area)
    final["serves_ej_community"] = final["serves_ej_community"].fillna(False).astype(bool)
    final["ej_area_fraction"] = final["ej_area_fraction"].fillna(0.0)
    final["ej_population_overlapped"] = final["ej_population_overlapped"].fillna(0.0)
    for c in ("any_income", "any_minority", "any_english"):
        final[c] = final[c].fillna(False).astype(bool)
    final["ej_criteria_distinct"] = final["ej_criteria_distinct"].fillna(0).astype(int)

    final.to_file(CLEAN / "pws_features_final.gpkg", driver="GPKG")
    final.drop(columns="geometry").to_csv(CLEAN / "pws_features_final.csv", index=False)
    print(f"\nWrote pws_features_final.gpkg and .csv  ({len(final)} rows)")


if __name__ == "__main__":
    main()
