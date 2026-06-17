import json
import boto3
import io
import pandas as pd

s3 = boto3.client("s3")

# Bucket unique Data Lake (corrigé — était "nyc-taxi-silver")
BUCKET = "nyc-taxi-platform"
SILVER_PREFIX = "silver/weather_clean/"


def lambda_handler(event, context):
    """
    GET /weather
    Retourne la météo moyenne depuis Silver weather_clean
    """
    try:
        # Lister les fichiers parquet dans silver/weather_clean/
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=BUCKET, Prefix=SILVER_PREFIX)

        dfs = []
        for page in pages:
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.endswith(".parquet"):
                    continue
                response = s3.get_object(Bucket=BUCKET, Key=key)
                df = pd.read_parquet(io.BytesIO(response["Body"].read()))
                dfs.append(df)

        if not dfs:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "No weather data found in silver/weather_clean/"})
            }

        df = pd.concat(dfs, ignore_index=True)

        # Colonnes attendues issues de Open-Meteo
        result = {}
        if "temperature_2m" in df.columns:
            result["avg_temperature_c"] = round(float(df["temperature_2m"].mean()), 2)
            result["min_temperature_c"] = round(float(df["temperature_2m"].min()), 2)
            result["max_temperature_c"] = round(float(df["temperature_2m"].max()), 2)

        if "precipitation" in df.columns:
            result["total_precipitation_mm"] = round(float(df["precipitation"].sum()), 2)

        result["records_count"] = len(df)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(result)
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
