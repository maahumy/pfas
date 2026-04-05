"""
05_21e_crossref.py

Identify MassDEP 21E contaminated sites that are:
  1. Located within a source-water protection polygon (Zone II or IWPA) of a PWS
  2. Whose site name contains keywords suggesting PFAS-relevant activity
  3. AND whose associated PWS has NOT been tested under UCMR5

These are the "priority investigation" sites for follow-up PFAS sampling.

Inputs (data/cleaned/):
  sites_21e.gpkg, zone2.gpkg, iwpa.gpkg, pws_features_engineered.csv

Outputs:
  data/cleaned/21e_pfas_relevant_in_zone2.gpkg
  data/cleaned/21e_priority_investigation.gpkg + .csv

Run from pfas-risk-ma/:
  python scripts/05_21e_crossref.py
"""

from pathlib import Path
import warnings
import pandas as pd
import geopandas as gpd

warnings.filterwarnings("ignore", message=".*CRS.*")

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "cleaned"

# Keywords in site names/addresses suggesting PFAS-relevant activity
PFAS_KEYWORDS = [
    # Industrial processes known to use PFAS
    "plating", "chrome", "chromium", "metal finish",
    "semiconductor", "electronics", "textile", "paper mill",
    "coating", "polymer", "plastic",
    # Fire-fighting foam / fire training (AFFF)
    "fire", "afff", "foam", "fire station", "fire dept",
    # Waste disposal
    "landfill", "dump", "waste disposal", "transfer station", "incinerator",
    # Military / defense
    "military", "air force", "army", "national guard", "air base",
    "defense", "dod", "hanscom", "otis", "westover", "devens", "natick",
    # Petroleum (some PFAS association via fuel additives and AFFF)
    "petroleum", "fuel", "gasoline", "gas station", "service station",
    "oil co", "ust", "underground storage",
    # Chemical manufacturing / cleaners
    "chemical", "solvent", "manufacturing", "chem co",
    "dry clean", "laundry",
    # Airports (AFFF training historically)
    "airport", "airfield", "airpark",
]


def contains_keyword(text: str):
    """Return (matched: bool, keyword or None)."""
    if not isinstance(text, str):
        return False, None
    t = text.lower()
    for kw in PFAS_KEYWORDS:
        if kw in t:
            return True, kw
    return False, None


def main():
    sites = gpd.read_file(CLEAN / "sites_21e.gpkg")
    zone2 = gpd.read_file(CLEAN / "zone2.gpkg")
    iwpa = gpd.read_file(CLEAN / "iwpa.gpkg")
    features = pd.read_csv(CLEAN / "pws_features_engineered.csv", dtype={"PWSID": str})

    print(f"21E sites: {len(sites)}")
    print(f"Zone II polygons: {len(zone2)}")
    print(f"IWPA polygons: {len(iwpa)}")
    print(f"21E cols: {sites.columns.tolist()}")

    # Spatial join: 21E sites WITHIN Zone II (keep PWS_ID from Zone II)
    z2 = zone2[["PWS_ID", "SUPPLIER", "TOWN", "ZII_NUM", "geometry"]].rename(
        columns={"TOWN": "zone2_town", "SUPPLIER": "zone2_supplier"}
    )
    sites_in_z2 = gpd.sjoin(sites, z2, how="inner", predicate="within").reset_index(drop=True)
    sites_in_z2["protection_type"] = "Zone II"
    print(f"\n21E sites inside a Zone II polygon: {len(sites_in_z2)}")

    # Also cover IWPA (transient systems)
    iwpa_slim = iwpa[["PWS_ID", "SUPPLIER", "TOWN", "geometry"]].rename(
        columns={"TOWN": "zone2_town", "SUPPLIER": "zone2_supplier"}
    )
    sites_in_iwpa = gpd.sjoin(sites, iwpa_slim, how="inner", predicate="within").reset_index(drop=True)
    sites_in_iwpa["protection_type"] = "IWPA"
    sites_in_iwpa["ZII_NUM"] = None
    print(f"21E sites inside an IWPA polygon: {len(sites_in_iwpa)}")

    # Use Zone II as primary; add only IWPA rows with RTNs not already in Zone II.
    z2_rtns = set(sites_in_z2["RTN"])
    iwpa_new = sites_in_iwpa[~sites_in_iwpa["RTN"].isin(z2_rtns)].reset_index(drop=True)
    # Keep only columns present in both
    common_cols = [c for c in sites_in_z2.columns if c in iwpa_new.columns]
    combined = pd.concat([sites_in_z2[common_cols], iwpa_new[common_cols]], ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs=sites.crs)
    print(f"Combined (Zone II + IWPA additions): {len(combined)}")

    # Keyword scan (NAME is the only free-text field in 21E)
    flags = combined["NAME"].apply(contains_keyword)
    combined["pfas_relevant"] = flags.apply(lambda t: t[0])
    combined["matching_keyword"] = flags.apply(lambda t: t[1])
    pfas_relevant = combined[combined["pfas_relevant"]].copy()
    print(f"\nPFAS-relevant 21E sites in protection areas: {len(pfas_relevant)}")
    print("Top keywords:")
    print(pfas_relevant["matching_keyword"].value_counts().head(10).to_string())

    # Normalize PWS_ID for join
    pfas_relevant["PWSID"] = "MA" + pfas_relevant["PWS_ID"].astype(str).str.strip().str.zfill(7)
    features["PWSID"] = features["PWSID"].astype(str).str.strip().str.upper()

    # Cross-reference with testing status
    pfas_relevant = pfas_relevant.merge(
        features[["PWSID", "in_ucmr5", "pfas_detected", "pws_name"]],
        on="PWSID", how="left"
    )
    pfas_relevant["in_ucmr5"] = pfas_relevant["in_ucmr5"].fillna(False).astype(bool)

    # Priority: PFAS-relevant AND in protection area AND NOT tested
    priority = pfas_relevant[~pfas_relevant["in_ucmr5"]].copy()
    print(f"\nPRIORITY INVESTIGATION SITES: {len(priority)}")
    print("(PFAS-relevant 21E sites in protection areas of UNTESTED systems)")

    # Outputs
    pfas_relevant.to_file(CLEAN / "21e_pfas_relevant_in_zone2.gpkg", driver="GPKG")
    priority.to_file(CLEAN / "21e_priority_investigation.gpkg", driver="GPKG")
    priority.drop(columns="geometry").to_csv(
        CLEAN / "21e_priority_investigation.csv", index=False
    )
    print(f"\nWrote 21e_pfas_relevant_in_zone2.gpkg ({len(pfas_relevant)} rows)")
    print(f"Wrote 21e_priority_investigation.gpkg ({len(priority)} rows)")

    # Spot check: print top 10
    print(f"\n=== Sample priority sites ===")
    cols = ["RTN", "NAME", "TOWN", "matching_keyword", "protection_type",
            "PWSID", "pws_name"]
    print(priority[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
