import pandas as pd
import boto3
import requests
import io
from datetime import datetime

S3_BUCKET = "nyc-taxi-platform"
s3 = boto3.client("s3")

def fetch_taxi_data():
    url = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"
    print(f"Downloading taxi data from {url}...")
    
    # Utiliser requests avec headers pour éviter le 403
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, stream=True)
    response.raise_for_status()
    
    df = pd.read_parquet(io.BytesIO(response.content))
    df = df.dropna(subset=["tpep_pickup_datetime", "tpep_dropoff_datetime"])
    print(f"Downloaded {len(df):,} rows")
    return df

def upload_to_s3(df):
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    file_name = f"taxi_{timestamp}.parquet"
    local_path = f"/tmp/{file_name}"
    df.to_parquet(local_path, index=False)
    s3.upload_file(local_path, S3_BUCKET, f"bronze/taxi/{file_name}")
    print(f"Uploaded to s3://{S3_BUCKET}/bronze/taxi/{file_name}")

if __name__ == "__main__":
    df = fetch_taxi_data()
    upload_to_s3(df)
