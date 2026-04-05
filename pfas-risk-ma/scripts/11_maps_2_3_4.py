"""
11_maps_2_3_4.py

Produce Maps 2, 3, and 4 as PNG + PDF (200 dpi).

  Map 2: Predicted PFAS risk (color) for untested systems
  Map 3: Predicted risk x EJ overlay (high-risk red vs lower-risk gold over EJ polygons)
  Map 4: 21E priority investigation sites within Zone II polygons

Inputs (data/cleaned/):
  towns.gpkg, ej_populations.gpkg, zone2.gpkg, sites_21e.gpkg,
  pws_features_final.gpkg, predicted_risk_scores.csv,
  21e_priority_investigation.gpkg

Outputs:
  maps/map2_predicted_risk.png + .pdf
  maps/map3_risk_ej_overlay.png + .pdf
  maps/map4_21e_priority_sites.png + .pdf

Run from pfas-risk-ma/:
  python scripts/11_maps_2_3_4.py
"""

from pathlib import Path
import warnings
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import pandas as pd

warnings.filterwarnings("ignore", message=".*CRS.*")

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "cleaned"
MAPS = ROOT / "maps"
MAPS.mkdir(parents=True, exist_ok=True)


def setup_ma_map(ax, towns, title):
    towns.boundary.plot(ax=ax, linewidth=0.3, color="#888888", zorder=1)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.set_axis_off()
    ax.text(0.99, 0.01,
            "Data: EPA UCMR 5 | MassGIS | MassDEP\nMap: M. Yousuf, EIT",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=7, color="#555555",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="none", alpha=0.85))


def main():
    towns = gpd.read_file(CLEAN / "towns.gpkg")
    pws = gpd.read_file(CLEAN / "pws_features_final.gpkg")
    predicted = pd.read_csv(CLEAN / "predicted_risk_scores.csv", dtype={"PWSID": str})
    ej = gpd.read_file(CLEAN / "ej_populations.gpkg")
    zone2 = gpd.read_file(CLEAN / "zone2.gpkg")
    all_21e = gpd.read_file(CLEAN / "sites_21e.gpkg")
    priority = gpd.read_file(CLEAN / "21e_priority_investigation.gpkg")

    # Merge predictions back
    pws = pws.merge(
        predicted[["PWSID", "predicted_risk_score", "risk_category"]],
        on="PWSID", how="left"
    )
    untested = pws[~pws["in_ucmr5"].astype(bool)].dropna(subset=["predicted_risk_score"])
    tested = pws[pws["in_ucmr5"].astype(bool)]

    # ======= MAP 2 =======
    fig, ax = plt.subplots(figsize=(13, 11))
    setup_ma_map(ax, towns,
                 "Predicted PFAS Contamination Risk — Untested MA Public Water Systems")
    tested.plot(ax=ax, color="lightgray", markersize=3, alpha=0.5, zorder=2)
    cmap = plt.cm.RdYlGn_r
    norm = mcolors.Normalize(vmin=0, vmax=1)
    untested.plot(ax=ax, column="predicted_risk_score", cmap=cmap, norm=norm,
                  markersize=14, edgecolor="white", linewidth=0.2, zorder=3)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm); sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.45, aspect=28,
                         label="Predicted PFAS risk score")
    cbar.ax.tick_params(labelsize=8)
    # note: MWRA area in Boston metro shows no data (different risk profile)
    ax.text(0.01, 0.99,
            "Note: Boston-metro MWRA-served communities are shown as gray\n"
            "tested dots (MWRA sources are in central MA reservoirs, not shown here).",
            transform=ax.transAxes, fontsize=7.5, va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow",
                      edgecolor="#aaaaaa", alpha=0.9))
    plt.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(MAPS / f"map2_predicted_risk.{ext}",
                    dpi=200 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)
    print("Wrote map2_predicted_risk.png + .pdf")

    # ======= MAP 3 =======
    fig, ax = plt.subplots(figsize=(13, 11))
    setup_ma_map(ax, towns,
                 "Predicted PFAS Risk x EJ Communities — Untested MA Public Water Systems")
    ej.plot(ax=ax, color="lavender", edgecolor="plum", linewidth=0.25, alpha=0.55, zorder=2)
    high_risk = untested[untested["predicted_risk_score"] > 0.5]
    lower_risk = untested[untested["predicted_risk_score"] <= 0.5]
    lower_risk.plot(ax=ax, color="gold", markersize=10, alpha=0.7,
                    edgecolor="white", linewidth=0.2, zorder=3)
    high_risk.plot(ax=ax, color="red", markersize=26,
                   edgecolor="darkred", linewidth=0.4, zorder=4)
    legend_elements = [
        Patch(facecolor="lavender", edgecolor="plum",
              label="EJ block groups (2020)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="red", markersize=10,
               markeredgecolor="darkred",
               label=f"High-risk untested (score > 0.5, n={len(high_risk)})"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="gold", markersize=7,
               label=f"Lower-risk untested (n={len(lower_risk)})"),
    ]
    ax.legend(handles=legend_elements, loc="lower left", fontsize=9, framealpha=0.95,
              title="Classification", title_fontproperties={"weight": "bold"})
    plt.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(MAPS / f"map3_risk_ej_overlay.{ext}",
                    dpi=200 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)
    print("Wrote map3_risk_ej_overlay.png + .pdf")

    # ======= MAP 4 =======
    fig, ax = plt.subplots(figsize=(13, 11))
    setup_ma_map(
        ax, towns,
        "21E Priority Investigation Sites — PFAS-Relevant 21E Sites in Untested Source-Water Protection Areas"
    )
    zone2.plot(ax=ax, color="lightcyan", edgecolor="steelblue",
               linewidth=0.25, alpha=0.45, zorder=2)
    all_21e.plot(ax=ax, color="gray", markersize=2, alpha=0.20, zorder=3)
    priority.plot(ax=ax, color="darkred", markersize=55, marker="^",
                  edgecolor="black", linewidth=0.5, zorder=4)
    legend_elements = [
        Patch(facecolor="lightcyan", edgecolor="steelblue",
              label="Source-water protection areas (Zone II)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="darkred", markersize=11,
               markeredgecolor="black",
               label=f"Priority investigation sites (n={len(priority)})"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="gray", markersize=5,
               alpha=0.6, label=f"All 21E sites (n={len(all_21e)})"),
    ]
    ax.legend(handles=legend_elements, loc="lower left", fontsize=9, framealpha=0.95,
              title="Classification", title_fontproperties={"weight": "bold"})
    plt.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(MAPS / f"map4_21e_priority_sites.{ext}",
                    dpi=200 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)
    print("Wrote map4_21e_priority_sites.png + .pdf")


if __name__ == "__main__":
    main()
