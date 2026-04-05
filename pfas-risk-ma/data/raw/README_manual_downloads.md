# Manual Downloads

These datasets require browser-based interaction and cannot be reliably scripted.

## EEA Drinking Water Portal PFAS Results (MassDEP)

The MassDEP EEA Data Portal serves drinking water testing results through an interactive
JavaScript app. Automated/API access is not documented; the portal is interactive-only.

**Steps:**

1. Open https://eeaonline.eea.state.ma.us/Portal/#!/search/drinking-water
2. In the search form, set:
   - **Contaminant Group**: `PFAS` (or search chemical name `PFAS6`)
   - Leave other filters unrestricted (all towns, all systems, full date range)
3. Click **Search**.
4. After results load, click the **Export** / **Download CSV** button.
5. Save the exported file to this directory as:
   ```
   pfas-risk-ma/data/raw/eea_pfas_drinking_water.csv
   ```
6. Record the download date in a comment at the top of the file (or in a sidecar note)
   so downstream cleaning scripts can track data vintage.

**Note:** UCMR5 is the primary source for the Week 0 insurance map. The EEA data is
supplementary and can be merged in later weeks once downloaded.

## Other manual / verification steps

- **MassGIS Public Water Supply Sources**: if the automated shapefile download in
  `03a_download_pws.sh` fails, visit
  https://www.mass.gov/info-details/massgis-data-public-water-supplies and download
  the current shapefile manually into `pfas-risk-ma/data/raw/massgis_pws/`.

- **Military Installations**: HIFLD's military shapefile URL changes periodically.
  A hand-curated MA-only fallback is provided at
  `pfas-risk-ma/data/raw/military_ma_manual.csv`.
