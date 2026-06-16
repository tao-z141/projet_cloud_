import requests
import pandas as pd
import boto3
from datetime import datetime

S3_BUCKET = "nyc-taxi-bronze"
s3 = boto3.client("s3")

def fetch_taxi_data():
    url = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"
    df = pd.read_parquet(url)
    return df

def upload_to_s3(df):
    file_name = f"taxi_{datetime.now().strftime('%Y%m%d%H%M%S')}.parquet"

    local_path = f"/tmp/{file_name}"
    df.to_parquet(local_path)

    s3.upload_file(local_path, S3_BUCKET, f"taxi/{file_name}")

    print("Uploaded to S3 Bronze")

if __name__ == "__main__":
    df = fetch_taxi_data()
    upload_to_s3(df)
