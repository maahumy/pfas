# Deployment — Streamlit Community Cloud

## Prerequisites
- GitHub repository (public or connected to your Streamlit account)
- Streamlit Community Cloud account (free): https://streamlit.io/cloud

## Steps
1. Visit https://share.streamlit.io and click **New app**.
2. Connect this GitHub repo.
3. Set:
   - Branch: `main` (or whichever branch holds the merged PR)
   - Main file path: `pfas-risk-ma/app/streamlit_app.py`
   - Requirements file: `pfas-risk-ma/app/requirements.txt` (Streamlit
     will detect this automatically)
4. Click **Deploy**.

## Post-deployment
- The app URL will be `https://<app-name>.streamlit.app`.
- Add the URL to the project README, resume, and LinkedIn.
- Verify all four tabs render, the town selector filters correctly, and
  the CSV download button works.

## Local testing

```bash
cd pfas-risk-ma
pip install -r app/requirements.txt
streamlit run app/streamlit_app.py
```

The app reads all its data from `app/data/`, which is populated by
`scripts/12_prepare_app_data.py`. If data files are missing, run that
script first.

## Troubleshooting

- **streamlit-folium fails on Streamlit Cloud** — switch the map tab to
  Plotly's `scatter_mapbox`, which is natively supported and has no
  native-lib dependencies.
- **App is slow** — the "All Massachusetts" map caps at 800 markers for
  performance; drill into a town via the sidebar for full detail.
- **Map doesn't render** — check browser console for errors; some
  CartoDB tiles can be blocked by corporate proxies. Folium falls back
  to OpenStreetMap.
