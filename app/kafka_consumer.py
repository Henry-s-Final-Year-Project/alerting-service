import json
import logging
import os
from kafka import KafkaConsumer
from datetime import datetime
import csv


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.getenv("KAFKA_BROKER")
KAFKA_ALERTS_TOPIC = os.getenv("KAFKA_ALERTS_TOPIC")
ALERTING_GROUP_ID = os.getenv("ALERTING_GROUP_ID")
FRAUD_THRESHOLD = float(os.getenv("FRAUD_THRESHOLD", 0.3))


def start_alerting_consumer():
    consumer = KafkaConsumer(
        KAFKA_ALERTS_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id=ALERTING_GROUP_ID,
    )

    logger.info("Alerting service listening on %s …", KAFKA_ALERTS_TOPIC)

    for msg in consumer:
        alert = msg.value
        transaction = alert["original_transaction"]
        outputs = alert["prediction"]["outputs"][0]["data"]
        fraud_probability = outputs[1]  # index 1 = fraud probability

        try:
            t_ingest_str = transaction["ingest_timestamp"]
            cleaned = t_ingest_str.rstrip("Z")[:26]
            t_ingest = datetime.fromisoformat(cleaned)
            t_now = datetime.utcnow()
            latency_ms = (t_now - t_ingest).total_seconds() * 1000
            logger.info("⏱️ End-to-End Latency: %.2f ms", latency_ms)

            with open("latency_log.csv", "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        t_ingest_str,  # Timestamp when data entered the system
                        t_now.isoformat(),  # Timestamp when alert was triggered
                        round(latency_ms, 2),  # End-to-end latency in ms
                    ]
                )
        except Exception as e:
            logger.error("Failed to compute latency: %s", e)

        if fraud_probability >= FRAUD_THRESHOLD:
            logger.warning(
                "⚠️  FRAUD DETECTED! Probability: %.2f\nTransaction: %s",
                fraud_probability,
                transaction,
            )
        else:
            logger.info("Transaction OK: fraud probability %f", fraud_probability)
