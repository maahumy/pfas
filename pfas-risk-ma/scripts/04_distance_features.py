"""
04_distance_features.py

For every MassGIS PWS source point, compute distances (in meters) to the nearest
PFAS-source-candidate feature (airport, military, landfill, POTW, industrial),
plus within-buffer counts. Aggregate to per-PWSID and merge with the UCMR5
summary to create the feature-engineered dataset for modeling.

Inputs (from data/cleaned/):
  pws_points.gpkg, airports.gpkg, military.gpkg, landfills.gpkg,
  wwtp_potw.gpkg, industrial.gpkg, mwra_service.gpkg
Input (from data/cleaned/ from Week 0):
  ucmr5_ma_system_summary.csv

Outputs:
  data/cleaned/pws_features_engineered.gpkg
  data/cleaned/pws_features_engineered.csv

Run from pfas-risk-ma/:
  python scripts/04_distance_features.py
"""

from pathlib import Path
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

warnings.filterwarnings("ignore", message=".*CRS.*")

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "cleaned"


def target_coords(gdf):
    """Return Nx2 array of x,y. Uses centroid for polygon layers."""
    geom_type = gdf.geometry.iloc[0].geom_type
    if geom_type in ("Polygon", "MultiPolygon"):
        cen = gdf.geometry.centroid
        return np.column_stack([cen.x, cen.y])
    return np.column_stack([gdf.geometry.x, gdf.geometry.y])


def nearest_distance(source_coords, target_gdf):
    tgt = target_coords(target_gdf)
    tree = cKDTree(tgt)
    dists, _ = tree.query(source_coords, k=1)
    return dists  # meters (EPSG:26986)


def count_within(source_coords, target_gdf, radius_m):
    tgt = target_coords(target_gdf)
    tree = cKDTree(tgt)
    return np.array([len(tree.query_ball_point(p, radius_m)) for p in source_coords])


def normalize_pwsid(series):
    """Convert bare 7-digit PWS_IDs to UCMR5 format: 'MA' + 7-digit zero-pad."""
    s = series.astype(str).str.strip().str.upper()
    # Already has MA prefix?
    needs_prefix = ~s.str.startswith("MA")
    s.loc[needs_prefix] = "MA" + s.loc[needs_prefix].str.zfill(7)
    return s


def main():
    # Anchor: MassGIS PWS source points (3990 rows)
    pws = gpd.read_file(CLEAN / "pws_points.gpkg")
    print(f"PWS source points: {len(pws)}")
    print(f"TYPE value counts:\n{pws['TYPE'].value_counts().to_string()}\n")

    source_xy = np.column_stack([pws.geometry.x, pws.geometry.y])

    # Load target layers
    targets = {
        "airport":    gpd.read_file(CLEAN / "airports.gpkg"),
        "military":   gpd.read_file(CLEAN / "military.gpkg"),
        "landfill":   gpd.read_file(CLEAN / "landfills.gpkg"),
        "wwtp":       gpd.read_file(CLEAN / "wwtp_potw.gpkg"),
        "industrial": gpd.read_file(CLEAN / "industrial.gpkg"),
    }

    # Nearest-distance features
    for name, tgt in targets.items():
        d = nearest_distance(source_xy, tgt)
        pws[f"dist_{name}_m"] = d
        pws[f"dist_{name}_km"] = d / 1000.0

    # Within-buffer counts for landfills + industrial (the ones with many instances)
    for radius_km in (1, 3, 5, 10):
        r_m = radius_km * 1000
        pws[f"landfills_within_{radius_km}km"] = count_within(source_xy, targets["landfill"], r_m)
        pws[f"industrial_within_{radius_km}km"] = count_within(source_xy, targets["industrial"], r_m)

    # Groundwater flag from TYPE (GW = community GW, NTNC/TNC/SW also exist)
    pws["source_type"] = pws["TYPE"].astype(str)
    pws["is_groundwater"] = pws["source_type"].str.startswith("GW") | pws["source_type"].isin(["EGW"])

    # MWRA flag via spatial join to MWRA-water service polygons (CODE in W, WS)
    mwra = gpd.read_file(CLEAN / "mwra_service.gpkg")
    mwra_water = mwra[mwra["CODE"].isin(["W", "WS"])].copy()
    joined = gpd.sjoin(pws[["geometry"]], mwra_water[["geometry"]], how="left", predicate="within")
    pws["is_mwra"] = joined["index_right"].notna().values

    # PWSID normalization
    pws["PWSID"] = normalize_pwsid(pws["PWS_ID"])

    # Aggregate to per-PWSID using min distance (most conservative) + first-point metadata
    agg_dist_cols = {c: "min" for c in pws.columns if c.startswith("dist_")}
    agg_count_cols = {c: "max" for c in pws.columns if "_within_" in c}
    agg_flag_cols = {"is_groundwater": "any", "is_mwra": "any"}

    agg_dict = {**agg_dist_cols, **agg_count_cols, **agg_flag_cols}
    agg_dict["source_type"] = lambda s: s.mode().iloc[0] if len(s.mode()) else s.iloc[0]
    agg_dict["SITE_NAME"] = "first"
    agg_dict["TOWN"] = "first"
    agg_dict["PWS_ID"] = "count"  # number of source points

    per_pws = pws.groupby("PWSID", as_index=False).agg(agg_dict)
    per_pws = per_pws.rename(columns={"PWS_ID": "num_sources"})
    print(f"Unique PWSIDs: {len(per_pws)}")
    print(f"MWRA-flagged PWSs: {per_pws['is_mwra'].sum()}")
    print(f"Groundwater PWSs: {per_pws['is_groundwater'].sum()}")

    # Merge with UCMR5 summary
    summary = pd.read_csv(CLEAN / "ucmr5_ma_system_summary.csv", dtype={"PWSID": str})
    summary["PWSID"] = summary["PWSID"].astype(str).str.strip().str.upper()
    print(f"\nUCMR5 summary systems: {len(summary)}")
    matched = summary["PWSID"].isin(per_pws["PWSID"]).sum()
    print(f"UCMR5 systems matched to PWSDEP: {matched}/{len(summary)}")

    merged = per_pws.merge(summary, on="PWSID", how="left")
    merged["in_ucmr5"] = merged["PWSID"].isin(summary["PWSID"])
    merged["pfas_detected"] = merged["any_detection"]  # NaN for non-UCMR5 systems

    # Put geometry back: use first source point per PWSID
    first_geom = pws.drop_duplicates("PWSID", keep="first").set_index("PWSID")["geometry"]
    merged_gdf = gpd.GeoDataFrame(
        merged, geometry=merged["PWSID"].map(first_geom).values, crs=pws.crs
    )

    out_gpkg = CLEAN / "pws_features_engineered.gpkg"
    out_csv = CLEAN / "pws_features_engineered.csv"
    merged_gdf.to_file(out_gpkg, driver="GPKG")
    merged_gdf.drop(columns="geometry").to_csv(out_csv, index=False)

    print(f"\n=== Feature engineering output ===")
    print(f"  Total PWSs (PWSDEP): {len(merged_gdf)}")
    print(f"  In UCMR5 with results: {merged_gdf['in_ucmr5'].sum()}")
    print(f"  PFAS detected (UCMR5): {merged_gdf['pfas_detected'].sum():.0f}")
    print(f"  Not in UCMR5 (prediction targets): {(~merged_gdf['in_ucmr5']).sum()}")

    dist_cols = [c for c in merged_gdf.columns if c.startswith("dist_") and c.endswith("_km")]
    print(f"\n=== Distance summary (km) ===")
    print(merged_gdf[dist_cols].describe().round(2).to_string())

    print(f"\nWrote {out_gpkg}")
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
