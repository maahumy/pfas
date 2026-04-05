"""
Massachusetts PFAS Contamination Risk Screening Tool — Streamlit app.

Run locally from pfas-risk-ma/:
    streamlit run app/streamlit_app.py
"""

from pathlib import Path
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"

st.set_page_config(
    page_title="MA PFAS Risk Screening Tool",
    page_icon="🔬",
    layout="wide",
)

st.title("Massachusetts PFAS Contamination Risk Screening Tool")
st.markdown(
    "An interactive screening tool for Massachusetts public water systems, "
    "integrating EPA UCMR 5 monitoring data, proximity-based risk prediction, "
    "MassDEP 21E contaminated-site cross-referencing, and state-defined "
    "environmental justice criteria."
)
st.caption(
    "This is a screening-level tool for prioritizing further investigation — "
    "not a risk assessment or compliance determination."
)


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_DIR / "pws_app_data.csv", dtype={"PWSID": str})
    priority = pd.read_csv(DATA_DIR / "priority_21e.csv")
    try:
        ej_text = (DATA_DIR / "ej_disparity_results.txt").read_text(encoding="utf-8")
    except Exception:
        ej_text = "EJ disparity results not available."
    try:
        model_meta = (DATA_DIR / "model_meta.txt").read_text(encoding="utf-8")
    except Exception:
        model_meta = ""
    return df, priority, ej_text, model_meta


df, priority_21e, ej_results_text, model_meta = load_data()


# ---------------- Sidebar ----------------
st.sidebar.header("Select location")

towns_list = sorted(df["TOWN"].dropna().unique().tolist())
selected_town = st.sidebar.selectbox(
    "Town / city", ["All Massachusetts"] + towns_list, index=0
)

if selected_town == "All Massachusetts":
    filtered = df.copy()
else:
    filtered = df[df["TOWN"] == selected_town].copy()

if selected_town != "All Massachusetts" and len(filtered):
    label_col = filtered["pws_name"].fillna(filtered["SITE_NAME"]).fillna("Unknown")
    sys_labels = (label_col + " (" + filtered["PWSID"] + ")").tolist()
    choice = st.sidebar.selectbox(
        "Specific system (optional)",
        ["All systems in " + selected_town] + sys_labels,
    )
    if choice != "All systems in " + selected_town:
        pwsid = choice.rsplit("(", 1)[-1].rstrip(")")
        filtered = filtered[filtered["PWSID"] == pwsid]

st.sidebar.markdown("---")
st.sidebar.markdown("**About the risk score**")
st.sidebar.caption(
    "Predicted from a logistic regression trained on 220 UCMR5-tested MA systems "
    "using distance-to-nearest-source features (airport, military, landfill, "
    "WWTP-POTW, industrial discharger) plus a groundwater flag and counts of "
    "industrial/landfill sites within 5 km. Screening-level — test AUC 0.885, "
    "5-fold CV AUC 0.60."
)


# ---------------- Metrics ----------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Water systems", f"{len(filtered):,}")
with col2:
    n_tested = int(filtered["in_ucmr5"].fillna(False).astype(bool).sum())
    st.metric("UCMR5 tested", f"{n_tested:,}")
with col3:
    n_det = int((filtered["pfas_detected"] == True).sum())  # NaN-safe
    st.metric("PFAS detected", f"{n_det:,}")
with col4:
    untested_mask = ~filtered["in_ucmr5"].fillna(False).astype(bool)
    high_mask = filtered["predicted_risk_score"].fillna(0) > 0.5
    n_high = int((untested_mask & high_mask).sum())
    st.metric("High risk (untested)", f"{n_high:,}")


# ---------------- Tabs ----------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["Map view", "System details", "21E priority sites", "Environmental justice"]
)


def classify_color_and_status(row):
    in_ucmr5 = bool(row.get("in_ucmr5") == True)
    if in_ucmr5:
        if row.get("pfas_detected") == True:
            if row.get("ever_exceeded_ma_mmcl") == True:
                return "#67001f", "Exceeds MA MMCL (PFAS6 > 20 ppt)"
            if row.get("ever_exceeded_federal_mcl") == True:
                return "#d7301f", "Exceeds federal MCL (> 4 ppt PFOA/PFOS)"
            return "#fdae61", "Detected below MCL"
        return "#2ca02c", "Tested — no PFAS detection"
    risk = row.get("predicted_risk_score")
    if pd.isna(risk):
        return "#bdbdbd", "Untested — no prediction"
    if risk > 0.75:
        return "#67001f", f"Untested — risk {risk:.0%} (Very High)"
    if risk > 0.50:
        return "#d7301f", f"Untested — risk {risk:.0%} (High)"
    if risk > 0.25:
        return "#fdae61", f"Untested — risk {risk:.0%} (Moderate)"
    return "#bdbdbd", f"Untested — risk {risk:.0%} (Low)"


# ===== Tab 1: Map =====
with tab1:
    st.subheader("PFAS detection and risk map")

    if selected_town == "All Massachusetts":
        center_lat, center_lon, zoom = 42.25, -71.8, 8
    else:
        center_lat = float(filtered["latitude"].mean())
        center_lon = float(filtered["longitude"].mean())
        zoom = 12

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom,
                   tiles="CartoDB positron")

    # Cap displayed markers for performance when "All MA" selected
    map_df = filtered
    if selected_town == "All Massachusetts" and len(map_df) > 800:
        map_df = map_df.sort_values("predicted_risk_score", ascending=False,
                                    na_position="last").head(800)
        st.caption(f"Showing 800 highest-risk or tested systems of {len(filtered):,} "
                   "for map performance. Use the sidebar to drill into a town.")

    for _, row in map_df.iterrows():
        if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")):
            continue
        color, status = classify_color_and_status(row)

        def _fmt(v, unit=""):
            return "n/a" if pd.isna(v) else f"{v:.1f}{unit}"

        popup_html = (
            f'<div style="width:280px;font-family:Arial;font-size:12px;">'
            f'<b>{row.get("pws_name") or row.get("SITE_NAME") or "Unknown"}</b><br>'
            f'PWSID: {row.get("PWSID","n/a")}<br>'
            f'Town: {row.get("TOWN","n/a")}<br>'
            f'Status: {status}<br>'
            f'<hr style="margin:5px 0">'
            f'Nearest airport: {_fmt(row.get("dist_airport_km"), " km")}<br>'
            f'Nearest military: {_fmt(row.get("dist_military_km"), " km")}<br>'
            f'Nearest landfill: {_fmt(row.get("dist_landfill_km"), " km")}<br>'
            f'Nearest WWTP (POTW): {_fmt(row.get("dist_wwtp_km"), " km")}<br>'
            f'Nearest industrial: {_fmt(row.get("dist_industrial_km"), " km")}<br>'
            f'<hr style="margin:5px 0">'
            f'EJ community: {"Yes" if row.get("serves_ej_community") else "No"}<br>'
            f'Source type: {row.get("source_type","n/a")}<br>'
            f'MWRA: {"Yes" if row.get("is_mwra") else "No"}<br>'
            f"</div>"
        )

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=6 if row.get("in_ucmr5") == True else 4,
            color=color, weight=1,
            fill=True, fill_color=color, fill_opacity=0.75,
            popup=folium.Popup(popup_html, max_width=320),
        ).add_to(m)

    st_folium(m, width=None, height=520, use_container_width=True,
              returned_objects=[])

    st.markdown(
        "**Legend:** "
        "<span style='color:#2ca02c'>●</span> tested, no detection &nbsp; "
        "<span style='color:#fdae61'>●</span> below MCL or moderate-risk untested &nbsp; "
        "<span style='color:#d7301f'>●</span> exceeds MCL / high-risk untested &nbsp; "
        "<span style='color:#67001f'>●</span> exceeds MA MMCL / very-high-risk untested &nbsp; "
        "<span style='color:#bdbdbd'>●</span> untested low-risk",
        unsafe_allow_html=True,
    )

# ===== Tab 2: System details =====
with tab2:
    st.subheader("System details")
    display_cols = [
        "PWSID", "pws_name", "SITE_NAME", "TOWN",
        "in_ucmr5", "pfas_detected",
        "max_pfoa_ppt", "max_pfos_ppt", "max_pfas6_sum_ppt",
        "predicted_risk_score", "risk_category",
        "dist_airport_km", "dist_military_km", "dist_landfill_km",
        "dist_wwtp_km", "dist_industrial_km",
        "is_groundwater", "is_mwra", "serves_ej_community",
    ]
    display_cols = [c for c in display_cols if c in filtered.columns]
    display = filtered[display_cols].copy()
    display = display.sort_values(
        "predicted_risk_score", ascending=False, na_position="last"
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.download_button(
        "Download filtered data (CSV)",
        display.to_csv(index=False),
        file_name=f"pfas_data_{selected_town.replace(' ', '_')}.csv",
        mime="text/csv",
    )

# ===== Tab 3: 21E priority sites =====
with tab3:
    st.subheader("21E priority investigation sites")
    st.markdown(
        "These MassDEP Chapter 21E contaminated sites are located inside the "
        "Zone II or IWPA source-water protection area of a public water system, "
        "have site names suggesting PFAS-relevant activity (AFFF/fire, fuel, "
        "dry cleaner, landfill, etc.), AND the associated water supply has "
        "**not** been tested under UCMR 5."
    )
    if selected_town != "All Massachusetts":
        p = priority_21e[priority_21e["TOWN"].astype(str).str.upper() ==
                         selected_town.upper()]
    else:
        p = priority_21e
    if p.empty:
        st.info("No priority investigation sites in this area.")
    else:
        st.metric("Priority sites", len(p))
        cols = [c for c in ["RTN", "NAME", "TOWN", "matching_keyword",
                            "protection_type", "PWSID", "pws_name",
                            "SITE_INFO"] if c in p.columns]
        st.dataframe(p[cols], use_container_width=True, hide_index=True)

# ===== Tab 4: EJ =====
with tab4:
    st.subheader("Environmental justice analysis")
    st.markdown(
        "Massachusetts defines EJ populations using four criteria: income "
        "(≤ 65% of statewide median), minority (≥ 40%), English-language "
        "isolation (≥ 25% of households), or combined minority + income. "
        "This analysis uses the official MassGIS 2020 EJ populations layer "
        "overlaid on MassDEP PWS service-area polygons."
    )
    st.code(ej_results_text, language="text")

    ej_sys = filtered[filtered["serves_ej_community"] == True]
    non_ej_sys = filtered[filtered["serves_ej_community"] != True]
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Serves EJ community**")
        st.metric("Count", f"{len(ej_sys):,}")
        if "predicted_risk_score" in ej_sys:
            mr = ej_sys["predicted_risk_score"].mean()
            st.metric("Mean predicted risk", f"{mr:.1%}" if pd.notna(mr) else "n/a")
    with col2:
        st.markdown("**Does not serve EJ community**")
        st.metric("Count", f"{len(non_ej_sys):,}")
        if "predicted_risk_score" in non_ej_sys:
            mr = non_ej_sys["predicted_risk_score"].mean()
            st.metric("Mean predicted risk", f"{mr:.1%}" if pd.notna(mr) else "n/a")


# ---------------- Footer ----------------
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:gray;font-size:12px;'>"
    "<b>Massachusetts PFAS Risk Screening Tool</b><br>"
    "Data: EPA UCMR 5 (Jan 2026 release) · MassGIS · MassDEP 21E · "
    "MassGIS 2020 EJ populations<br>"
    "Built by Maahum Yousuf, EIT<br>"
    "<i>Screening-level tool only — not a risk assessment, compliance "
    "determination, or regulatory recommendation.</i>"
    "</div>",
    unsafe_allow_html=True,
)
