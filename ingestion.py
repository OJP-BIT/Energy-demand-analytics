import os
import requests
import pandas as pd
import snowflake.connector
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load your .env file
load_dotenv()

# ── Fetch data from EIA API (with pagination) ─────────────────────────────────
def fetch_eia_demand(region, start, end):
    print(f"  Fetching {region} from EIA API...")
    url = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
    all_data = []
    offset = 0

    while True:
        params = {
            "api_key": os.getenv("EIA_API_KEY"),
            "frequency": "hourly",
            "data[0]": "value",
            "facets[type][]": "D",
            "facets[respondent][]": region,
            "start": start,
            "end": end,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": 5000,
            "offset": offset
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        batch = response.json()["response"]["data"]

        if not batch:
            break

        all_data.extend(batch)
        offset += 5000
        print(f"  Fetched {len(all_data)} rows so far...")

        if len(batch) < 5000:
            break

    if not all_data:
        print(f"  No data returned for {region}")
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df = df.rename(columns={
        "respondent": "region",
        "type": "demand_type",
        "value": "value_mwh"
    })
    df["period"] = pd.to_datetime(df["period"])
    df["value_mwh"] = pd.to_numeric(df["value_mwh"], errors="coerce")
    df = df[["region", "demand_type", "period", "value_mwh"]].dropna()
    print(f"  Got {len(df)} rows for {region}")
    return df

# ── Connect to Snowflake ──────────────────────────────────────────────────────
def get_snowflake_conn():
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database="ENERGY_DB",
        schema="RAW"
    )

# ── Load data into Snowflake ──────────────────────────────────────────────────
def load_to_snowflake(df, region):
    if df.empty:
        return

    print(f"  Loading {len(df)} rows to Snowflake for {region}...")
    conn = get_snowflake_conn()
    cursor = conn.cursor()

    rows = [
        (row.region, row.demand_type, str(row.period), row.value_mwh)
        for row in df.itertuples()
    ]

    cursor.executemany(
        """INSERT INTO RAW.HOURLY_DEMAND
           (REGION, DEMAND_TYPE, PERIOD, VALUE_MWH)
           VALUES (%s, %s, %s, %s)""",
        rows
    )
    conn.commit()
    cursor.close()
    conn.close()
    print(f"  Done loading {region}.\n")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    regions = ["ERCO", "PJM", "MISO"]
    end_date = datetime.today().strftime("%Y-%m-%dT%H")
    start_date = (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%dT%H")

    print(f"Starting ingestion: {start_date} to {end_date}\n")

    for region in regions:
        print(f"Processing {region}...")
        try:
            df = fetch_eia_demand(region, start_date, end_date)
            load_to_snowflake(df, region)
        except Exception as e:
            print(f"  ERROR for {region}: {e}\n")

    print("All done! Ingestion complete.")