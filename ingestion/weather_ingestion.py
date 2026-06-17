import requests
import json
import boto3
from datetime import datetime

s3 = boto3.client("s3")

BUCKET = "nyc-taxi-platform"


def fetch_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=40.7128"
        "&longitude=-74.0060"
        "&hourly=temperature_2m,precipitation"
        "&timezone=America/New_York"
    )

    response = requests.get(url)
    response.raise_for_status()

    return response.json()


def upload_weather(data):

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    file_name = f"weather_{timestamp}.json"

    s3.put_object(
        Bucket=BUCKET,
        Key=f"bronze/weather/{file_name}",
        Body=json.dumps(data),
        ContentType="application/json"
    )

    print(f"Uploaded: s3://{BUCKET}/bronze/weather/{file_name}")


if __name__ == "__main__":
    weather_data = fetch_weather()
    upload_weather(weather_data)
