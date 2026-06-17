from kafka import KafkaConsumer
import json
import boto3
from datetime import datetime

# =========================
# CONFIGURATION
# =========================

KAFKA_BROKER = "localhost:9092"  # à remplacer par EC2_PUBLIC_IP:9092

TOPIC = "taxi-stream-events"

S3_BUCKET = "nyc-taxi-platform"
DDB_TABLE = "realtime_events"

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DDB_TABLE)

# =========================
# KAFKA CONSUMER
# =========================

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=KAFKA_BROKER,
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    auto_offset_reset="latest",
    enable_auto_commit=True
)

# =========================
# FUNCTIONS
# =========================

def write_to_s3(event):

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    file_name = f"stream_{timestamp}.json"

    key = f"bronze/stream/{file_name}"

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(event),
        ContentType="application/json"
    )

    print(f"S3 written: s3://{S3_BUCKET}/{key}")


def write_to_dynamodb(event):

    item = {
        "taxi_id": str(event["taxi_id"]),
        "timestamp": str(event["timestamp"]),
        "pickup_lat": str(event["pickup_lat"]),
        "pickup_lon": str(event["pickup_lon"]),
        "speed": str(event["speed"]),
        "fare": str(event["fare"])
    }

    table.put_item(Item=item)

    print(f" DynamoDB updated: taxi_id={event['taxi_id']}")


# =========================
# MAIN LOOP
# =========================

if __name__ == "__main__":

    print("Kafka Consumer started...")

    for message in consumer:

        event = message.value

        print("received:", event)

        try:
            # 1. Stockage streaming S3 Bronze
            write_to_s3(event)

            # 2. Stockage temps réel DynamoDB
            write_to_dynamodb(event)

        except Exception as e:
            print("Error processing event:", e)
