import os
import pandas as pd
import snowflake.connector
from prophet import Prophet
from dotenv import load_dotenv

load_dotenv()

# ── Connect to Snowflake ──────────────────────────────────────────────────────
def get_snowflake_conn():
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database="ENERGY_DB",
        schema="ANALYTICS"
    )

# ── Create forecast table if it doesn't exist ─────────────────────────────────
def create_forecast_table():
    conn = get_snowflake_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ENERGY_DB.FORECASTS.DEMAND_FORECAST (
            REGION        VARCHAR(50),
            FORECAST_DATE DATE,
            YHAT          FLOAT,
            YHAT_LOWER    FLOAT,
            YHAT_UPPER    FLOAT,
            CREATED_AT    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """)
    cursor.execute("TRUNCATE TABLE ENERGY_DB.FORECASTS.DEMAND_FORECAST")
    conn.commit()
    cursor.close()
    conn.close()
    print("Forecast table ready.\n")

# ── Train Prophet and store results ──────────────────────────────────────────
def run_forecast(region):
    print(f"Training model for {region}...")

    conn = get_snowflake_conn()
    df = pd.read_sql(f"""
        SELECT DEMAND_DATE AS ds, AVG_DEMAND_MWH AS y
        FROM ENERGY_DB.ANALYTICS.DAILY_DEMAND
        WHERE REGION = '{region}'
        ORDER BY DEMAND_DATE
    """, conn)
    conn.close()

    # Fix: Snowflake returns column names in uppercase — Prophet needs lowercase
    df.columns = df.columns.str.lower()

    print(f"  Loaded {len(df)} days of training data")

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05
    )
    model.fit(df)

    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)

    future_only = forecast[forecast["ds"] > df["ds"].max()][
        ["ds", "yhat", "yhat_lower", "yhat_upper"]
    ].copy()

    print(f"  Storing {len(future_only)} forecast rows for {region}...")

    conn = get_snowflake_conn()
    cursor = conn.cursor()

    rows = [
        (region, str(row.ds.date()), row.yhat, row.yhat_lower, row.yhat_upper)
        for row in future_only.itertuples()
    ]
    cursor.executemany(
        """INSERT INTO ENERGY_DB.FORECASTS.DEMAND_FORECAST
           (REGION, FORECAST_DATE, YHAT, YHAT_LOWER, YHAT_UPPER)
           VALUES (%s, %s, %s, %s, %s)""",
        rows
    )
    conn.commit()
    cursor.close()
    conn.close()
    print(f"  Done — {region} forecast stored.\n")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    create_forecast_table()

    for region in ["ERCO", "PJM", "MISO"]:
        try:
            run_forecast(region)
        except Exception as e:
            print(f"  ERROR for {region}: {e}\n")

    print("All forecasts complete!")