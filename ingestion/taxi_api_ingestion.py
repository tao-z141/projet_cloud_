import pandas as pd
import boto3
from datetime import datetime

# Bucket unique (Data Lake)
S3_BUCKET = "nyc-taxi-platform"
s3 = boto3.client("s3")


def fetch_taxi_data():
    url = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"
    df = pd.read_parquet(url)

    # Petit nettoyage léger (important pour Silver ensuite)
    df = df.dropna(subset=["tpep_pickup_datetime", "tpep_dropoff_datetime"])

    return df


def upload_to_s3(df):

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    file_name = f"taxi_{timestamp}.parquet"

    local_path = f"/tmp/{file_name}"

    # Sauvegarde locale
    df.to_parquet(local_path, index=False)

    # Upload vers BRONZE (médaillon)
    s3.upload_file(
        local_path,
        S3_BUCKET,
        f"bronze/taxi/{file_name}"
    )

    print(f"Uploaded to s3://{S3_BUCKET}/bronze/taxi/{file_name}")


if __name__ == "__main__":
    df = fetch_taxi_data()
    upload_to_s3(df)
