# pfas-risk-ma

Massachusetts PFAS Risk Prediction & Environmental Justice Analysis.

A screening-level model that predicts PFAS-detection risk for the ~1,600
Massachusetts public water systems that have NOT been sampled under EPA UCMR 5,
using distance-based features to known PFAS sources (airports, military sites,
landfills, POTW outfalls, and industrial dischargers), and tests whether the
high-risk population disproportionately serves EJ communities.

## Data sources

| Source | Dataset | URL | Downloaded |
|---|---|---|---|
| EPA | UCMR 5 occurrence data (by-state zip, `UCMR5_All_MA_WY.txt`) | https://www.epa.gov/system/files/other-files/2023-08/ucmr5-occurrence-data-by-state.zip | 2026-04-04 |
| MassGIS | Public Water Supply Sources (`PWSDEP_PT.shp`) | `shapefiles/state/pwsdep_pt.zip` | 2026-04-04 |
| MassGIS | 2020 Environmental Justice Populations (`EJ_POLY.shp`) | `shapefiles/census2020/ej2020.zip` | 2026-04-04 |
| MassGIS | 2020 Census Towns (`CENSUS2020TOWNS_POLY.shp`) | `shapefiles/census2020/CENSUS2020TOWNS_SHP.zip` | 2026-04-04 |
| MassGIS | 21E contaminated sites (`C21E_PT.shp`) | `shapefiles/state/c21e_pt.zip` | 2026-04-04 |
| MassGIS | Solid Waste / Landfills (`SW_LD_POLY.shp`) | `shapefiles/state/solidwaste.zip` | 2026-04-04 |
| MassGIS | Zone II / IWPA protection areas | `shapefiles/state/zone2_zone1_iwpa.zip` | 2026-04-04 |
| MassGIS | PWS water-service area polygons | `shapefiles/state/DEP_PWS_Water_Service_Areas.zip` | 2026-04-04 |
| MassGIS | POTW sewer service areas (WWTP proxy) | `shapefiles/state/DEP_Sewer_Service_Areas.zip` | 2026-04-04 |
| MassGIS | MWRA service polygons | `shapefiles/state/mwraservice.zip` | 2026-04-04 |
| MassGIS | BWP major polluters (industrial dischargers) | `shapefiles/state/bwpmajor_pt.zip` | 2026-04-04 |
| OurAirports | MA airports (filtered) | https://davidmegginson.github.io/ourairports-data/airports.csv | 2026-04-04 |
| MassDEP | EEA Drinking Water Portal PFAS results | https://eeaonline.eea.state.ma.us/Portal/#!/search/drinking-water | manual — see `data/raw/README_manual_downloads.md` |
| Manual | Known MA military installations (7 sites) | `data/raw/military_ma_manual.csv` | 2026-04-04 |

All MassGIS layers live under the common prefix
`https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/`.

## Reproducing

```bash
pip install -r requirements.txt
cd pfas-risk-ma
python scripts/01_clean_pfas_data.py      # Week 0: clean UCMR5
python scripts/02_preliminary_map.py      # Week 0: Map 1
python scripts/03_standardize_layers.py   # reproject all layers to EPSG:26986
python scripts/04_distance_features.py    # distance-to-source features per PWS
python scripts/05_21e_crossref.py         # 21E priority investigation sites
python scripts/06_ej_overlay.py           # EJ service-area overlay
python scripts/07_prepare_model_data.py   # train/predict split
python scripts/08_train_model.py          # LR + RF, selects best
python scripts/09_predict_risk.py         # score untested systems
python scripts/10_ej_disparity_test.py    # chi-square + Mann-Whitney
python scripts/11_maps_2_3_4.py           # final maps 2, 3, 4
```

## Methodology notes

- **Units & thresholds**: UCMR5 reports in µg/L; model uses ng/L (ppt). Non-detects
  are imputed at MRL/2. Federal MCL (2024): PFOA, PFOS each 4.0 ppt. MA MMCL:
  sum of PFAS6 ≤ 20 ppt (PFAS6 = PFOA, PFOS, PFHxS, PFNA, PFHpA, PFDA).
- **CRS**: all layers reprojected to EPSG:26986 (MA State Plane, meters) for
  distance/area computations.
- **PWSID normalization**: MassGIS uses 7-digit numeric; UCMR5 uses "MA" + 7-digit.
  Both reconciled to "MA"+zero-padded form at every join.
- **MWRA flag**: 62 MA towns receive MWRA water/sewer; 30 PWSs in this dataset
  are MWRA-associated. Kept in training with a flag since their sources (central
  MA reservoirs) produce distance features that are legitimately different.
- **WWTP proxy**: using POTW service-area polygon centroids in lieu of a
  standalone WWTP point layer.
- **Industrial proxy**: MassDEP BWP major polluters (`BWPMAJOR_PT`, n=2,445).
  A subset of all industrial PFAS sources, but curated and publicly tracked.
- **21E text search**: 21E schema does not include structured contaminant
  fields — keyword search is over the `NAME` column only.
- **Model choice**: Logistic regression selected over random forest for
  interpretability; LR test AUC 0.885, 5-fold CV AUC 0.60 (screening level).

## Week 0 snapshot (from UCMR5)

- 46,070 PFAS results across 263 MA public water systems.
- 143 / 263 PWSs showed ≥1 detection.
- 106 ever exceeded federal MCL; 34 ever exceeded MA MMCL.

## Week 5–6 results

- **1,818 MA PWS source points** geolocated (from MassGIS PWSDEP_PT).
- **220 / 263** UCMR5 systems matched to a MassGIS source point (training set).
- **1,598 untested systems** scored by the model (prediction set).
- **Risk distribution (untested)**: 966 Low · 486 Moderate · 142 High · 4 Very High.
- **EJ disparity**: statistically significant. 42.9% of untested systems in EJ
  service areas are classified high-risk vs. 8.1% in non-EJ areas (**5.3×**).
  - Chi-square: χ² = 65.1, p < 0.0001
  - Mann-Whitney U (one-sided EJ > non-EJ): p < 0.0001
- **21E priority investigation sites**: 7 PFAS-relevant 21E sites fall inside
  the Zone II / IWPA protection area of an UNTESTED public water system.

## Directory layout

```
pfas-risk-ma/
├── data/
│   ├── raw/             # UCMR5, MassGIS shapefiles, CSVs
│   └── cleaned/         # .gpkg layers (EPSG:26986), model data, predictions
├── scripts/             # 01–11, numbered pipeline
├── maps/                # Map 1–4 + model_evaluation + feature_importance
├── README.md
└── requirements.txt
```
