from kafka import KafkaConsumer
import json
import boto3
import uuid
from datetime import datetime

# =========================
# CONFIGURATION
# =========================
# Remplacer par l'IP publique EC2 après déploiement CloudFormation
# Ex: KAFKA_BROKER = "54.12.34.56:9092"
KAFKA_BROKER = "35.180.91.209:9092"

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
    enable_auto_commit=True,
    group_id="nyc-taxi-consumer-group"
)


# =========================
# FUNCTIONS
# =========================

def write_to_s3(event):
    timestamp = datetime.utcnow().strftime("%Y/%m/%d/%H%M%S")
    event_id = str(uuid.uuid4())
    key = f"bronze/stream/{timestamp}_{event_id}.json"

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(event),
        ContentType="application/json"
    )
    print(f"S3 written: s3://{S3_BUCKET}/{key}")


def write_to_dynamodb(event):
    # event_id est la clé primaire définie dans le schéma DynamoDB
    # (corrigé: l'ancienne version n'incluait pas event_id)
    item = {
        "event_id": str(uuid.uuid4()),          # clé primaire HASH
        "taxi_id": str(event["taxi_id"]),
        "timestamp": str(event["timestamp"]),
        "pickup_lat": str(round(event["pickup_lat"], 2)),   # généralisation RGPD
        "pickup_lon": str(round(event["pickup_lon"], 2)),   # généralisation RGPD
        "dropoff_lat": str(round(event["dropoff_lat"], 2)),
        "dropoff_lon": str(round(event["dropoff_lon"], 2)),
        "speed": str(event["speed"]),
        "fare": str(event["fare"]),
        "ingested_at": datetime.utcnow().isoformat()
    }

    table.put_item(Item=item)
    print(f"DynamoDB updated: taxi_id={event['taxi_id']}")


# =========================
# MAIN LOOP
# =========================

if __name__ == "__main__":
    print(f"Kafka Consumer started on {KAFKA_BROKER}, topic={TOPIC}")

    for message in consumer:
        event = message.value
        print("received:", event)

        try:
            write_to_s3(event)
            write_to_dynamodb(event)

        except Exception as e:
            print(f"Error processing event: {e}")
