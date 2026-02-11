from confluent_kafka import Consumer, KafkaException, Message
from typing import Optional


class KafkaConsumer:

    TOPICS = [
        "gps_pings",
        "trips",
        "driver_status",
        "surge_updates",
        "ratings",
        "payments",
        "driver_profiles",
        "rider_profiles",
    ]

    def __init__(self, bootstrap_servers: str, group_id: str):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self._consumer: Optional[Consumer] = None

    @property
    def subscribed_topics(self) -> list[str]:
        return self.TOPICS

    @property
    def consumer_group(self) -> str:
        return self.group_id

    def _ensure_consumer(self) -> None:
        if self._consumer is None:
            config: dict[str, str | int | float | bool | None] = {
                "bootstrap.servers": self.bootstrap_servers,
                "group.id": self.group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
            self._consumer = Consumer(config)
            self._consumer.subscribe(self.TOPICS)

    def poll(self, timeout: float = 1.0) -> Optional[Message]:
        self._ensure_consumer()
        assert self._consumer is not None
        msg = self._consumer.poll(timeout=timeout)

        if msg is None:
            return None

        if msg.error():
            raise KafkaException(msg.error())

        return msg

    def commit(self, messages: Optional[list[Message]] = None) -> None:
        self._ensure_consumer()
        assert self._consumer is not None
        if messages:
            self._consumer.commit(asynchronous=False)
        else:
            self._consumer.commit(asynchronous=False)

    def close(self) -> None:
        if self._consumer:
            self._consumer.close()
