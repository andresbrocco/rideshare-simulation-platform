from confluent_kafka import Producer


class KafkaProducer:
    """Thin wrapper around confluent-kafka Producer with sensible defaults."""

    def __init__(self, config: dict):
        producer_config = {**config, "acks": "all"}
        self._producer = Producer(producer_config)

    def produce(self, topic: str, key: str, value: str, callback=None):
        self._producer.produce(topic, key=key, value=value, on_delivery=callback)
        self._producer.poll(0)

    def close(self):
        self._producer.flush()
