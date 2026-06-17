from kafka import KafkaProducer
import json
import time
import random

# EC2 Kafka public/private IP (à adapter après deploy CloudFormation)
KAFKA_BROKER = "localhost:9092"

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

# NYC bounding box (approx Manhattan)
NYC_LAT_MIN = 40.70
NYC_LAT_MAX = 40.85
NYC_LON_MIN = -74.02
NYC_LON_MAX = -73.90


def generate_event():
    return {
        "taxi_id": random.randint(1000, 9999),
        "pickup_lat": random.uniform(NYC_LAT_MIN, NYC_LAT_MAX),
        "pickup_lon": random.uniform(NYC_LON_MIN, NYC_LON_MAX),
        "dropoff_lat": random.uniform(NYC_LAT_MIN, NYC_LAT_MAX),
        "dropoff_lon": random.uniform(NYC_LON_MIN, NYC_LON_MAX),
        "speed": random.randint(5, 90),
        "fare": round(random.uniform(5, 80), 2),
        "timestamp": time.time()
    }


if __name__ == "__main__":

    print(" Starting NYC Taxi Kafka Producer...")

    while True:
        event = generate_event()

        producer.send("taxi-stream-events", event)

        print("sent:", event)

        time.sleep(2)
