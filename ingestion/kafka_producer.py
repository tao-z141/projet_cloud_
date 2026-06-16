from kafka import KafkaProducer
import json
import time
import random

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

while True:
    event = {
        "taxi_id": random.randint(1000, 9999),
        "lat": 48.85 + random.random() / 100,
        "lon": 2.35 + random.random() / 100,
        "speed": random.randint(10, 80),
        "timestamp": time.time()
    }

    producer.send("taxi-stream", event)
    print("sent:", event)

    time.sleep(2)
