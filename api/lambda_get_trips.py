import json
import boto3
import io
import pandas as pd

s3 = boto3.client("s3")

# Bucket unique Data Lake (corrigé — était "nyc-taxi-gold")
BUCKET = "nyc-taxi-platform"
GOLD_PREFIX = "gold/kpi_daily/"


def lambda_handler(event, context):
    """
    GET /trips
    Query params optionnels:
      - date_from : YYYY-MM-DD
      - date_to   : YYYY-MM-DD
    """
    try:
        # Lister les fichiers parquet dans gold/kpi_daily/
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=BUCKET, Prefix=GOLD_PREFIX)

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
                "body": json.dumps({"error": "No data found in gold/kpi_daily/"})
            }

        df = pd.concat(dfs, ignore_index=True)

        # Filtres optionnels par date
        query_params = event.get("queryStringParameters") or {}
        date_from = query_params.get("date_from")
        date_to = query_params.get("date_to")

        if "day" in df.columns:
            df["day"] = pd.to_datetime(df["day"])
            if date_from:
                df = df[df["day"] >= date_from]
            if date_to:
                df = df[df["day"] <= date_to]

        response_body = {
            "total_trips": int(df["nb_trips"].sum()),
            "avg_distance_km": round(float(df["avg_distance_km"].mean()), 2),
            "avg_fare_usd": round(float(df["avg_fare_usd"].mean()), 2),
            "total_revenue_usd": round(float(df["total_revenue_usd"].sum()), 2),
            "days_count": len(df),
        }

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response_body)
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
