import requests
import json
import boto3
from datetime import datetime

s3 = boto3.client("s3")
BUCKET = "nyc-taxi-platform"

def fetch_weather_historical():
    """
    Récupère la météo historique de NYC pour janvier 2024
    via Open-Meteo Historical API (gratuite, pas de clé requise)
    Correspond exactement à la période des données taxi
    """
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        "?latitude=40.7128"
        "&longitude=-74.0060"
        "&start_date=2024-01-01"
        "&end_date=2025-03-31"
        "&hourly=temperature_2m,precipitation,windspeed_10m,weathercode"
        "&timezone=America/New_York"
    )
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def upload_weather(data):
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    file_name = f"weather_historical_{timestamp}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=f"bronze/weather/{file_name}",
        Body=json.dumps(data),
        ContentType="application/json"
    )
    print(f"Uploaded: s3://{BUCKET}/bronze/weather/{file_name}")
    print(f"Records: {len(data['hourly']['time'])} hours")

if __name__ == "__main__":
    print("Fetching NYC weather history January 2024...")
    weather_data = fetch_weather_historical()
    upload_weather(weather_data)
