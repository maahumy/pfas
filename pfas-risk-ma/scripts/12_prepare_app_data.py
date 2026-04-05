"""
12_prepare_app_data.py

Build a lightweight data package for the Streamlit app under app/data/.
Extracts WGS84 lat/lon from the GeoPackage, trims columns, and copies the
EJ disparity results text file.

Inputs:
  data/cleaned/pws_features_final.gpkg
  data/cleaned/predicted_risk_scores.csv
  data/cleaned/21e_priority_investigation.csv
  data/cleaned/ej_disparity_results.txt
  data/cleaned/model_meta.txt

Outputs:
  app/data/pws_app_data.csv
  app/data/priority_21e.csv
  app/data/ej_disparity_results.txt
  app/data/model_meta.txt

Run from pfas-risk-ma/:
  python scripts/12_prepare_app_data.py
"""

from pathlib import Path
import shutil
import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "cleaned"
APP_DATA = ROOT / "app" / "data"
APP_DATA.mkdir(parents=True, exist_ok=True)


def main():
    gdf = gpd.read_file(CLEAN / "pws_features_final.gpkg").to_crs("EPSG:4326")
    gdf["latitude"] = gdf.geometry.y
    gdf["longitude"] = gdf.geometry.x
    df = pd.DataFrame(gdf.drop(columns="geometry"))

    preds = pd.read_csv(CLEAN / "predicted_risk_scores.csv",
                        dtype={"PWSID": str})[
        ["PWSID", "predicted_risk_score", "risk_category"]
    ]
    merged = df.merge(preds, on="PWSID", how="left")

    keep = [
        "PWSID", "pws_name", "SITE_NAME", "TOWN", "latitude", "longitude",
        "in_ucmr5", "pfas_detected",
        "max_pfoa_ppt", "max_pfos_ppt", "max_pfas6_sum_ppt",
        "ever_exceeded_federal_mcl", "ever_exceeded_ma_mmcl",
        "predicted_risk_score", "risk_category",
        "dist_airport_km", "dist_military_km", "dist_landfill_km",
        "dist_industrial_km", "dist_wwtp_km",
        "landfills_within_5km", "industrial_within_5km",
        "is_groundwater", "is_mwra", "source_type",
        "serves_ej_community", "ej_area_fraction",
        "any_income", "any_minority", "any_english",
    ]
    keep = [c for c in keep if c in merged.columns]

    out_main = APP_DATA / "pws_app_data.csv"
    merged[keep].to_csv(out_main, index=False)

    priority = pd.read_csv(CLEAN / "21e_priority_investigation.csv")
    out_priority = APP_DATA / "priority_21e.csv"
    priority.to_csv(out_priority, index=False)

    shutil.copy(CLEAN / "ej_disparity_results.txt",
                APP_DATA / "ej_disparity_results.txt")
    if (CLEAN / "model_meta.txt").exists():
        shutil.copy(CLEAN / "model_meta.txt", APP_DATA / "model_meta.txt")

    print(f"Wrote {out_main}  ({len(merged)} systems, {len(keep)} cols)")
    print(f"Wrote {out_priority}  ({len(priority)} priority sites)")
    print(f"Copied ej_disparity_results.txt and model_meta.txt")


if __name__ == "__main__":
    main()
