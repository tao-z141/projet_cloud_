import boto3
import requests

s3 = boto3.client("s3")
BUCKET = "nyc-taxi-platform"

def fetch_and_upload_zones():
    """
    Télécharge le fichier de référence des zones NYC Taxi
    et l'upload dans S3 bronze/zones/
    """
    url = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
    print(f"Downloading zones lookup from {url}...")
    response = requests.get(url)
    response.raise_for_status()

    s3.put_object(
        Bucket=BUCKET,
        Key="bronze/zones/taxi_zone_lookup.csv",
        Body=response.content,
        ContentType="text/csv"
    )
    print(f"Uploaded: s3://{BUCKET}/bronze/zones/taxi_zone_lookup.csv")
    print(f"Size: {len(response.content)} bytes")

if __name__ == "__main__":
    fetch_and_upload_zones()
