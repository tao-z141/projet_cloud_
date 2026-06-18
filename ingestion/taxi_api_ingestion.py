import pandas as pd
import boto3
import requests
import io
from datetime import datetime

S3_BUCKET = "nyc-taxi-platform"
s3 = boto3.client("s3")

MONTHS = [
    "2024-01",
    "2024-02",
    "2024-03",
    "2024-04"
]

def fetch_taxi_data(month):
    url = f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"
    print(f"Downloading {month}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, stream=True)
    response.raise_for_status()
    df = pd.read_parquet(io.BytesIO(response.content))
    df = df.dropna(subset=["tpep_pickup_datetime", "tpep_dropoff_datetime"])
    print(f"  {month}: {len(df):,} rows")
    return df

def upload_to_s3(df, month):
    file_name = f"taxi_{month}.parquet"
    local_path = f"/tmp/{file_name}"
    df.to_parquet(local_path, index=False)
    s3.upload_file(local_path, S3_BUCKET, f"bronze/taxi/{file_name}")
    print(f"  Uploaded: s3://{S3_BUCKET}/bronze/taxi/{file_name}")

if __name__ == "__main__":
    for month in MONTHS:
        df = fetch_taxi_data(month)
        upload_to_s3(df, month)
    print("All months ingested!")
