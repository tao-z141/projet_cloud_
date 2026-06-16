import json
import boto3
import pandas as pd

s3 = boto3.client("s3")

BUCKET = "nyc-taxi-silver"

def lambda_handler(event, context):

    obj = s3.get_object(
        Bucket=BUCKET,
        Key="weather_clean/"
    )

    df = pd.read_json(obj["Body"])

    return {
        "statusCode": 200,
        "body": json.dumps({
            "avg_temperature": float(df["temperature_2m"].mean())
        })
    }
