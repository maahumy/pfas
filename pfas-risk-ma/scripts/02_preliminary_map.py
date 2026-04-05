"""
02_preliminary_map.py

Produce the Week 0 draft map of known PFAS detections in Massachusetts
public water systems. Two outputs:

  1. Static map (PNG + PDF) via matplotlib + geopandas -- portfolio-ready
  2. Interactive map (HTML) via folium -- for quick exploration

Inputs:
  data/cleaned/ucmr5_ma_system_summary.csv
  data/raw/massgis_pws/PWSDEP_PT.shp
  data/raw/massgis_towns/CENSUS2020TOWNS_POLY.shp

Outputs:
  maps/pfas_detections_ma.png
  maps/pfas_detections_ma.pdf
  maps/pfas_detections_ma_interactive.html

Run from the pfas-risk-ma/ directory:
  python scripts/02_preliminary_map.py
"""

from pathlib import Path
import warnings

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import folium

warnings.filterwarnings("ignore", message=".*CRS.*")

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "cleaned"
MAPS = ROOT / "maps"
MAPS.mkdir(parents=True, exist_ok=True)

# Massachusetts State Plane (meters) for static map
MA_SP_EPSG = 26986


def load_and_join():
    """Load shapefiles + summary, reconcile PWSID formats, return joined GeoDataFrame."""
    towns = gpd.read_file(RAW / "massgis_towns" / "CENSUS2020TOWNS_POLY.shp")
    pws = gpd.read_file(RAW / "massgis_pws" / "PWSDEP_PT.shp")
    summary = pd.read_csv(CLEAN / "ucmr5_ma_system_summary.csv", dtype={"PWSID": str})

    # Detect the PWSID column in the MassGIS layer
    id_candidates = [c for c in pws.columns if c.upper() in ("PWSID", "PWS_ID", "SYSTEMID")]
    if not id_candidates:
        raise RuntimeError(
            f"Cannot find PWSID column in PWSDEP_PT. Columns present: "
            f"{pws.columns.tolist()}"
        )
    pws_id_col = id_candidates[0]
    print(f"PWSDEP_PT columns (first 15): {pws.columns.tolist()[:15]}")
    print(f"Using '{pws_id_col}' as PWSID key")

    # Reconcile PWSID format. UCMR5 uses e.g. 'MA1234567'.
    # MassGIS PWSDEP_PT typically uses either 'MA1234567' or just '1234567'.
    pws[pws_id_col] = pws[pws_id_col].astype(str).str.strip()
    sample_id = pws[pws_id_col].dropna().iloc[0]
    if not sample_id.upper().startswith("MA"):
        pws[pws_id_col] = "MA" + pws[pws_id_col].str.zfill(7)
    pws[pws_id_col] = pws[pws_id_col].str.upper()

    # Some PWS have many sampling sites. De-duplicate by PWSID (keep first point).
    pws_dedup = pws.drop_duplicates(subset=[pws_id_col], keep="first").copy()

    joined = pws_dedup.merge(
        summary, left_on=pws_id_col, right_on="PWSID", how="left"
    )
    print(f"Joined: {joined['PWSID'].notna().sum()} / {len(summary)} "
          f"systems located on map")

    return towns, joined


def classify(row) -> str:
    """Return one of: not_tested, no_detection, below_mcl, above_fed_mcl, above_ma_mmcl."""
    if pd.isna(row.get("any_detection")):
        return "not_tested"
    if not row["any_detection"]:
        return "no_detection"
    if row.get("ever_exceeded_ma_mmcl"):
        return "above_ma_mmcl"
    if row.get("ever_exceeded_federal_mcl"):
        return "above_fed_mcl"
    return "below_mcl"


CATEGORY_STYLE = {
    # category: (color, radius, legend label, zorder)
    "not_tested":    ("#bdbdbd", 8,  "Not in UCMR5 sample",             1),
    "no_detection":  ("#2ca02c", 10, "Tested, no PFAS detection",       2),
    "below_mcl":     ("#fdae61", 14, "Detected below MCL",              3),
    "above_fed_mcl": ("#d7301f", 18, "Exceeds federal MCL (4 ppt PFOA/PFOS)", 4),
    "above_ma_mmcl": ("#67001f", 22, "Exceeds MA MMCL (PFAS6 > 20 ppt)",       5),
}


def make_static_map(towns, joined):
    """matplotlib static map, PNG + PDF."""
    towns = towns.to_crs(epsg=MA_SP_EPSG)
    joined = joined.to_crs(epsg=MA_SP_EPSG)
    joined["category"] = joined.apply(classify, axis=1)

    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    towns.boundary.plot(ax=ax, linewidth=0.3, color="#888888", zorder=0)

    # Plot by category, bottom layer first
    for cat, (color, size, label, zorder) in sorted(
        CATEGORY_STYLE.items(), key=lambda x: x[1][3]
    ):
        subset = joined[joined["category"] == cat]
        if subset.empty:
            continue
        subset.plot(
            ax=ax,
            color=color,
            markersize=size,
            edgecolor="white",
            linewidth=0.3,
            label=f"{label} (n={len(subset)})",
            zorder=zorder,
        )

    ax.set_title(
        "Known PFAS Detections in Massachusetts Public Water Systems\n"
        "EPA UCMR 5 (2023-2025 monitoring cycle)",
        fontsize=15,
        fontweight="bold",
    )
    ax.set_axis_off()
    leg = ax.legend(loc="lower left", fontsize=9, frameon=True, framealpha=0.95)
    leg.set_title("Detection status", prop={"weight": "bold"})

    # Attribution
    ax.text(
        0.99, 0.01,
        "Data: EPA UCMR 5 (Jan 2026 release) | MassGIS PWSDEP_PT, Census2020 Towns\n"
        "Map: M. Yousuf, EIT",
        transform=ax.transAxes,
        ha="right", va="bottom",
        fontsize=7, color="#555555",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="none", alpha=0.8),
    )

    plt.tight_layout()
    png = MAPS / "map1_pfas_detections_ma.png"
    pdf = MAPS / "map1_pfas_detections_ma.pdf"
    plt.savefig(png, dpi=200, bbox_inches="tight")
    plt.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {png}")
    print(f"Wrote {pdf}")


def make_interactive_map(joined):
    """Folium interactive map."""
    joined = joined.to_crs(epsg=4326).copy()
    joined["category"] = joined.apply(classify, axis=1)

    m = folium.Map(location=[42.25, -71.8], zoom_start=8, tiles="CartoDB positron")

    for _, row in joined.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        color, size, label, _ = CATEGORY_STYLE[row["category"]]
        pwoa = row.get("max_pfoa_ppt")
        pwos = row.get("max_pfos_ppt")
        pf6 = row.get("max_pfas6_sum_ppt")
        parts = [
            f"<b>{row.get('pws_name') or row.get('PWSID') or 'Unknown'}</b>",
            f"PWSID: {row.get('PWSID', 'n/a')}",
            f"Status: {label}",
        ]
        if pd.notna(pwoa):
            parts.append(f"Max PFOA: {pwoa:.2f} ppt")
        if pd.notna(pwos):
            parts.append(f"Max PFOS: {pwos:.2f} ppt")
        if pd.notna(pf6):
            parts.append(f"Max PFAS6 sum: {pf6:.2f} ppt")
        popup_html = "<br>".join(parts)

        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=max(4, size / 3),
            color=color,
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            popup=folium.Popup(popup_html, max_width=320),
        ).add_to(m)

    # Legend
    legend_html = (
        '<div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;'
        ' background: white; padding: 10px 12px; border: 1px solid #888;'
        ' border-radius: 4px; font-family: sans-serif; font-size: 12px;">'
        '<b>PFAS detection status</b><br>'
    )
    for cat, (color, _, label, _) in sorted(
        CATEGORY_STYLE.items(), key=lambda x: x[1][3]
    ):
        legend_html += (
            f'<span style="display:inline-block;width:12px;height:12px;'
            f'background:{color};border-radius:50%;margin-right:6px;"></span>'
            f'{label}<br>'
        )
    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))

    out = MAPS / "map1_pfas_detections_ma_interactive.html"
    m.save(str(out))
    print(f"Wrote {out}")


def main():
    towns, joined = load_and_join()
    make_static_map(towns, joined)
    make_interactive_map(joined)


if __name__ == "__main__":
    main()
