# pfas-risk-ma

Massachusetts PFAS Risk Prediction & Environmental Justice Analysis — Week 0 data
foundation (the "insurance policy" workstream).

This repository holds a partially-complete PFAS dataset for Massachusetts public
water systems and a draft map of known PFAS detections. The full risk model, EJ
overlay, 21E cross-reference, and Streamlit app are scheduled for weeks 5–8.

## Data sources

| Source | Dataset | URL | Downloaded |
|---|---|---|---|
| EPA | UCMR 5 occurrence data (by-state zip, `UCMR5_All_MA_WY.txt`) | https://www.epa.gov/system/files/other-files/2023-08/ucmr5-occurrence-data-by-state.zip | 2026-04-04 |
| MassGIS | Public Water Supply Sources (`PWSDEP_PT.shp`) | https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/state/pwsdep_pt.zip | 2026-04-04 |
| MassGIS | 2020 Environmental Justice Populations (`EJ_POLY.shp`) | https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/census2020/ej2020.zip | 2026-04-04 |
| MassGIS | 2020 Census Towns (`CENSUS2020TOWNS_POLY.shp`) | https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/census2020/CENSUS2020TOWNS_SHP.zip | 2026-04-04 |
| OurAirports | MA airports, filtered from `airports.csv` | https://davidmegginson.github.io/ourairports-data/airports.csv | 2026-04-04 |
| MassDEP | EEA Drinking Water Portal PFAS results | https://eeaonline.eea.state.ma.us/Portal/#!/search/drinking-water | **manual — see** `data/raw/README_manual_downloads.md` |
| Manual | Known MA military installations (seven sites) | hand-curated in `data/raw/military_ma_manual.csv` | 2026-04-04 |

## Reproducing the Week 0 outputs

1. Install Python 3.11+ and create a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Downloads: the raw data has already been committed. To refresh, re-run
   downloads from the URLs above (or the helper commands in git history).
4. Clean the PFAS data:
   ```bash
   python scripts/01_clean_pfas_data.py
   ```
5. Produce the draft maps:
   ```bash
   python scripts/02_preliminary_map.py
   ```

Outputs land in `data/cleaned/` and `maps/`.

## Units, thresholds, and methodology notes

- UCMR 5 reports PFAS concentrations in **µg/L (ppb)**. The federal MCL and MA
  MMCL use **ng/L (ppt)**. Conversion: `1 µg/L = 1000 ng/L = 1000 ppt`.
  The cleaning script converts to ppt in the `concentration_ppt` column.
- **Non-detects** (rows where `AnalyticalResultsSign == "<"`) are substituted
  with **MRL / 2** — standard practice for environmental datasets.
- **Federal MCL (2024 rule):** PFOA and PFOS each 4.0 ppt (maximum contaminant
  level, individual compounds).
- **Massachusetts MMCL:** sum of PFAS6 ≤ 20 ppt, where
  PFAS6 = {PFOA, PFOS, PFHxS, PFNA, PFHpA, PFDA}.

## Directory layout

```
pfas-risk-ma/
├── data/
│   ├── raw/
│   │   ├── ucmr5_ma_pfas.csv                  # MA UCMR5 records, lithium removed
│   │   ├── README_manual_downloads.md         # EEA portal steps
│   │   ├── airports_ma.csv                    # 276 MA airports (OurAirports)
│   │   ├── military_ma_manual.csv             # 7 MA military sites
│   │   ├── massgis_pws/                       # PWSDEP_PT.shp and associates
│   │   ├── massgis_ej/                        # EJ_POLY.shp and associates
│   │   └── massgis_towns/                     # CENSUS2020TOWNS_POLY.shp, _ARC.shp
│   └── cleaned/                               # produced by scripts/01
├── scripts/
│   ├── 01_clean_pfas_data.py
│   └── 02_preliminary_map.py
├── maps/                                      # produced by scripts/02
├── README.md
└── requirements.txt
```

## Week 0 dataset snapshot

- 46,070 PFAS results across 263 MA public water systems (UCMR 5).
- 29 distinct PFAS analytes (lithium excluded).
