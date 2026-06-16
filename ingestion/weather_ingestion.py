import requests
import json
import boto3
from datetime import datetime

s3 = boto3.client("s3")
BUCKET = "nyc-taxi-bronze"

def fetch_weather():
    url = "https://api.open-meteo.com/v1/forecast?latitude=48.85&longitude=2.35&hourly=temperature_2m"
    response = requests.get(url)
    return response.json()

def upload_weather(data):
    file_name = f"weather_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"

    s3.put_object(
        Bucket=BUCKET,
        Key=f"weather/{file_name}",
        Body=json.dumps(data)
    )

if __name__ == "__main__":
    data = fetch_weather()
    upload_weather(data)
