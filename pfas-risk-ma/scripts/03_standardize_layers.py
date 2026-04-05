"""
03_standardize_layers.py

Reproject every input layer to EPSG:26986 (MA State Plane, meters) and save as
geopackages in data/cleaned/. Prints a summary table at the end.

Run from pfas-risk-ma/:
  python scripts/03_standardize_layers.py
"""

from pathlib import Path
import warnings

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

warnings.filterwarnings("ignore", message=".*CRS.*")

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "cleaned"
CLEAN.mkdir(parents=True, exist_ok=True)

TARGET_CRS = "EPSG:26986"

# (label, source path, output filename) — None source means CSV-with-lat-lon path handled below
SHAPEFILE_LAYERS = [
    ("pws_points",          RAW / "massgis_pws"              / "PWSDEP_PT.shp",                          "pws_points.gpkg"),
    ("towns",               RAW / "massgis_towns"            / "CENSUS2020TOWNS_POLY.shp",               "towns.gpkg"),
    ("ej_populations",      RAW / "massgis_ej"               / "EJ_POLY.shp",                            "ej_populations.gpkg"),
    ("sites_21e",           RAW / "massdep_21e"              / "C21E_PT.shp",                            "sites_21e.gpkg"),
    ("landfills",           RAW / "massdep_landfills"        / "SW_LD_POLY.shp",                         "landfills.gpkg"),
    ("wwtp_potw",           RAW / "wwtp_ma"                  / "SEWER_SERVICE_AREA_POTW_POLY.shp",       "wwtp_potw.gpkg"),
    ("wwtp_nonpotw",        RAW / "wwtp_ma"                  / "SEWER_SERVICE_AREA_NONPOTW_POLY.shp",    "wwtp_nonpotw.gpkg"),
    ("industrial",          RAW / "industrial_ma"            / "BWPMAJOR_PT.shp",                        "industrial.gpkg"),
    ("zone2",               RAW / "massgis_zone2"            / "ZONE2_POLY.shp",                         "zone2.gpkg"),
    ("iwpa",                RAW / "massgis_zone2"            / "IWPA_POLY.shp",                          "iwpa.gpkg"),
    ("pws_service_areas",   RAW / "massgis_pws_service_areas"/ "PWS_WATER_SERVICE_AREA_COMM_POLY.shp",   "pws_service_areas.gpkg"),
    ("mwra_service",        RAW / "mwra"                     / "MWRASERVICE_POLY.shp",                   "mwra_service.gpkg"),
]


def process_shp(label: str, path: Path, out_name: str):
    if not path.exists():
        return label, "MISSING", "-", "-", "-", "-"
    gdf = gpd.read_file(path)
    orig_crs = str(gdf.crs)
    geom_type = gdf.geometry.iloc[0].geom_type if len(gdf) else "empty"
    if gdf.crs is None:
        # MassGIS shapefiles should all be in 26986 — assume if .prj says so
        gdf = gdf.set_crs(TARGET_CRS)
    if str(gdf.crs).upper().replace("EPSG:", "") != "26986":
        gdf = gdf.to_crs(TARGET_CRS)
    out_path = CLEAN / out_name
    gdf.to_file(out_path, driver="GPKG")
    return label, len(gdf), geom_type, orig_crs, "EPSG:26986", out_path.name


def process_csv_points(label: str, csv_path: Path, lat_col: str, lon_col: str, out_name: str):
    if not csv_path.exists():
        return label, "MISSING", "-", "-", "-", "-"
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=[lat_col, lon_col]).copy()
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])
    geom = [Point(xy) for xy in zip(df[lon_col], df[lat_col])]
    gdf = gpd.GeoDataFrame(df, geometry=geom, crs="EPSG:4326").to_crs(TARGET_CRS)
    out_path = CLEAN / out_name
    gdf.to_file(out_path, driver="GPKG")
    return label, len(gdf), "Point", "EPSG:4326", "EPSG:26986", out_path.name


def main():
    rows = []

    for label, path, out_name in SHAPEFILE_LAYERS:
        rows.append(process_shp(label, path, out_name))

    # CSVs
    rows.append(process_csv_points(
        "airports", RAW / "airports_ma.csv", "latitude_deg", "longitude_deg", "airports.gpkg"
    ))
    rows.append(process_csv_points(
        "military", RAW / "military_ma_manual.csv", "lat", "lon", "military.gpkg"
    ))

    # Summary table
    header = ("Layer", "Rows", "Geometry", "Original CRS", "Target CRS", "Saved to")
    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(6)]
    fmt = " | ".join(f"{{:<{w}}}" for w in widths)
    print()
    print(fmt.format(*header))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt.format(*(str(x) for x in r)))
    print()


if __name__ == "__main__":
    main()
