import json
import boto3
import pandas as pd

s3 = boto3.client("s3")

BUCKET = "nyc-taxi-gold"

def lambda_handler(event, context):

    obj = s3.get_object(
        Bucket=BUCKET,
        Key="trips_kpi/"
    )

    df = pd.read_parquet(obj["Body"])

    response = {
        "total_trips": int(df["nb_trips"].sum()),
        "avg_distance": float(df["avg_distance"].mean())
    }

    return {
        "statusCode": 200,
        "body": json.dumps(response)
    }
