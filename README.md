# ⚡ U.S. Energy Demand Forecasting & Anomaly Detection

End-to-end data analytics project for the energy industry — built to demonstrate SQL, forecasting, and dashboard skills for Data Analyst roles.

👉 **[View Live Dashboard](https://energy-demand-analytics-dmexmwbwzmqkejvgb2o6mf.streamlit.app/)**

---

## What This Project Does

Pulls real hourly electricity demand data from the U.S. EIA API for 3 major grid regions (ERCOT, PJM, MISO), stores and transforms it in Snowflake, forecasts the next 30 days using Facebook Prophet, and displays everything in an interactive dashboard.

---

## Tech Stack

| | Tool |
|---|---|
| Data Source | EIA Open Data API |
| Warehouse | Snowflake |
| Ingestion | Python |
| Transforms | SQL (window functions, CTEs) |
| Forecasting | Facebook Prophet |
| Dashboard | Streamlit + Plotly |

---

## Architecture

```
EIA API → Python (ingestion.py) → Snowflake RAW
                                       ↓ SQL transforms
                                  Snowflake ANALYTICS
                                       ↓ Prophet model
                                  Snowflake FORECASTS
                                       ↓
                                  Streamlit Dashboard
```

---

## Dashboard Features

- KPI cards — peak demand, average demand, MoM change
- Historical demand with 7-day and 30-day rolling averages
- 30-day forecast with confidence interval
- Month-over-month demand change chart
- Anomaly detection table (Z-score > 2.0)

---
## Run Locally

```bash
git clone https://github.com/OJP-BIT/Energy-demand-analytics.git
cd Energy-demand-analytics
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file:
```
EIA_API_KEY=your_key
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
```

```bash
python ingestion.py
python forecast.py
streamlit run app.py
```

---

## Cost

Built and deployed at **$0** — EIA API is free, Snowflake free trial, Streamlit Cloud free tier.

---

**Ojas** · [LinkedIn](https://www.linkedin.com/in/ojaspawar/) · [GitHub](https://github.com/OJP-BIT)
