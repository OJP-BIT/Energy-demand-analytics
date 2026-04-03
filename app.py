import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

def get_secret(key):
    try:
        return st.secrets[key]
    except:
        return os.getenv(key)

# TEMPORARY DEBUG - remove after fixing
st.write("USER:", get_secret("SNOWFLAKE_USER"))
st.write("ACCOUNT:", get_secret("SNOWFLAKE_ACCOUNT"))
st.write("WAREHOUSE:", get_secret("SNOWFLAKE_WAREHOUSE"))


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Energy Demand Analytics",
    page_icon="⚡",
    layout="wide"
)

# ── Snowflake connection ──────────────────────────────────────────────────────

def get_connection():
    return snowflake.connector.connect(
        user=get_secret("SNOWFLAKE_USER"),
        password=get_secret("SNOWFLAKE_PASSWORD"),
        account=get_secret("SNOWFLAKE_ACCOUNT"),
        warehouse=get_secret("SNOWFLAKE_WAREHOUSE"),
        database="ENERGY_DB",
        schema="ANALYTICS"
    )

# Use cursor instead of pd.read_sql to avoid NoneType errors

def run_query(query: str) -> pd.DataFrame:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    return pd.DataFrame(rows, columns=columns)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("⚡ Energy Analytics")
st.sidebar.markdown("U.S. ISO Electricity Demand")

region = st.sidebar.selectbox(
    "Select Region",
    options=["ERCO", "PJM", "MISO"],
    format_func=lambda x: {
        "ERCO": "ERCO — ERCOT (Texas)",
        "PJM":  "PJM — Mid-Atlantic",
        "MISO": "MISO — Midcontinent"
    }[x]
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Data source:** [EIA Open Data API](https://www.eia.gov/opendata/)  \n"
    "**Warehouse:** Snowflake  \n"
    "**Forecast model:** Facebook Prophet"
)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚡ U.S. Energy Demand Forecasting")
st.caption(f"Showing data for **{region}** · Refreshes every hour · Built with Snowflake + Prophet")

# ── KPI Metric Cards ──────────────────────────────────────────────────────────
try:
    kpi_df = run_query(f"""
        SELECT
            ROUND(MAX(PEAK_DEMAND_MWH), 0)  AS PEAK_MWH,
            ROUND(AVG(AVG_DEMAND_MWH), 0)   AS AVG_MWH,
            COUNT(*)                         AS TOTAL_DAYS
        FROM ENERGY_DB.ANALYTICS.DAILY_DEMAND
        WHERE REGION = '{region}'
    """)

    mom_df = run_query(f"""
        SELECT MOM_PCT_CHANGE
        FROM ENERGY_DB.ANALYTICS.MOM_DEMAND
        WHERE REGION = '{region}'
          AND MOM_PCT_CHANGE IS NOT NULL
        ORDER BY DEMAND_MONTH DESC
        LIMIT 1
    """)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Peak Demand", f"{int(kpi_df['PEAK_MWH'][0]):,} MWh")
    col2.metric("Avg Daily Demand", f"{int(kpi_df['AVG_MWH'][0]):,} MWh")
    col3.metric("Days of Data", f"{int(kpi_df['TOTAL_DAYS'][0]):,} days")
    mom_val = float(mom_df['MOM_PCT_CHANGE'][0]) if not mom_df.empty else 0
    col4.metric("MoM Change", f"{mom_val:+.1f}%", delta=f"{mom_val:+.1f}%")

except Exception as e:
    st.warning(f"Could not load KPI metrics: {e}")

st.markdown("---")

# ── Chart 1: Historical Demand + Rolling Averages ─────────────────────────────
st.subheader("📈 Historical Demand with Rolling Averages")

try:
    trend_df = run_query(f"""
        SELECT
            DEMAND_DATE,
            AVG_DEMAND_MWH,
            ROLLING_7DAY_AVG,
            ROLLING_30DAY_AVG
        FROM ENERGY_DB.ANALYTICS.ROLLING_DEMAND
        WHERE REGION = '{region}'
        ORDER BY DEMAND_DATE
    """)

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=trend_df["DEMAND_DATE"], y=trend_df["AVG_DEMAND_MWH"],
        name="Daily Avg", opacity=0.3,
        line=dict(color="#7B9EC8", width=1)
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend_df["DEMAND_DATE"], y=trend_df["ROLLING_7DAY_AVG"],
        name="7-Day Rolling Avg",
        line=dict(color="#2E75B6", width=2)
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend_df["DEMAND_DATE"], y=trend_df["ROLLING_30DAY_AVG"],
        name="30-Day Rolling Avg",
        line=dict(color="#1A4F8A", width=2.5)
    ))
    fig_trend.update_layout(
        height=380,
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis_title="Demand (MWh)",
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.2)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.2)")
    )
    st.plotly_chart(fig_trend, use_container_width=True)

except Exception as e:
    st.error(f"Could not load trend data: {e}")

# ── Chart 2: Forecast ─────────────────────────────────────────────────────────
st.subheader("🔮 30-Day Demand Forecast")

try:
    forecast_df = run_query(f"""
        SELECT FORECAST_DATE, YHAT, YHAT_LOWER, YHAT_UPPER
        FROM ENERGY_DB.FORECASTS.DEMAND_FORECAST
        WHERE REGION = '{region}'
        ORDER BY FORECAST_DATE
    """)

    actuals_df = run_query(f"""
        SELECT DEMAND_DATE, AVG_DEMAND_MWH
        FROM ENERGY_DB.ANALYTICS.DAILY_DEMAND
        WHERE REGION = '{region}'
        ORDER BY DEMAND_DATE DESC
        LIMIT 30
    """)
    actuals_df = actuals_df.sort_values("DEMAND_DATE")

    fig_fcst = go.Figure()
    fig_fcst.add_trace(go.Scatter(
        x=pd.concat([forecast_df["FORECAST_DATE"], forecast_df["FORECAST_DATE"][::-1]]),
        y=pd.concat([forecast_df["YHAT_UPPER"], forecast_df["YHAT_LOWER"][::-1]]),
        fill="toself",
        fillcolor="rgba(46,117,182,0.15)",
        line=dict(color="rgba(0,0,0,0)"),
        name="Confidence Interval",
        hoverinfo="skip"
    ))
    fig_fcst.add_trace(go.Scatter(
        x=actuals_df["DEMAND_DATE"], y=actuals_df["AVG_DEMAND_MWH"],
        name="Actual (last 30d)",
        line=dict(color="#888888", width=1.5, dash="dot")
    ))
    fig_fcst.add_trace(go.Scatter(
        x=forecast_df["FORECAST_DATE"], y=forecast_df["YHAT"],
        name="Forecast",
        line=dict(color="#2E75B6", width=2.5)
    ))
    fig_fcst.update_layout(
        height=380,
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis_title="Demand (MWh)",
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.2)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.2)")
    )
    st.plotly_chart(fig_fcst, use_container_width=True)

except Exception as e:
    st.error(f"Could not load forecast data: {e}")

# ── Chart 3: Month-over-Month ─────────────────────────────────────────────────
st.subheader("📊 Month-over-Month Demand Change")

try:
    mom_full_df = run_query(f"""
        SELECT DEMAND_MONTH, MONTHLY_TOTAL_MWH, MOM_PCT_CHANGE
        FROM ENERGY_DB.ANALYTICS.MOM_DEMAND
        WHERE REGION = '{region}'
          AND MOM_PCT_CHANGE IS NOT NULL
        ORDER BY DEMAND_MONTH
    """)

    colors = [
        "#2E75B6" if v >= 0 else "#C0392B"
        for v in mom_full_df["MOM_PCT_CHANGE"]
    ]

    fig_mom = go.Figure(go.Bar(
        x=mom_full_df["DEMAND_MONTH"],
        y=mom_full_df["MOM_PCT_CHANGE"],
        marker_color=colors,
        name="MoM % Change"
    ))
    fig_mom.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=20, b=0),
        yaxis_title="MoM Change (%)",
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(200,200,200,0.2)",
            zeroline=True,
            zerolinecolor="rgba(150,150,150,0.5)"
        )
    )
    st.plotly_chart(fig_mom, use_container_width=True)

except Exception as e:
    st.error(f"Could not load MoM data: {e}")

# ── Table: Anomalies ──────────────────────────────────────────────────────────
st.subheader("🚨 Detected Demand Anomalies")
st.caption("Hourly records with Z-score > 2.0 or < -2.0, sorted by severity")

try:
    anom_df = run_query(f"""
        SELECT
            TO_CHAR(PERIOD, 'YYYY-MM-DD HH24:MI')  AS TIMESTAMP,
            ROUND(VALUE_MWH, 0)                     AS DEMAND_MWH,
            ROUND(MEAN_DEMAND, 0)                   AS MEAN_MWH,
            ROUND(Z_SCORE, 2)                       AS Z_SCORE,
            STATUS
        FROM ENERGY_DB.ANALYTICS.ANOMALIES
        WHERE REGION = '{region}'
          AND STATUS = 'ANOMALY'
        ORDER BY ABS(Z_SCORE) DESC
        LIMIT 50
    """)

    st.dataframe(
        anom_df,
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error(f"Could not load anomaly data: {e}")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Built by Ojas · Data sourced from U.S. EIA Open Data API · "
    "Warehouse: Snowflake · Forecast: Facebook Prophet · "
    "[GitHub](https://github.com/OJP-BIT/Energy-demand-analytics) · [LinkedIn](https://linkedin.com)"
)