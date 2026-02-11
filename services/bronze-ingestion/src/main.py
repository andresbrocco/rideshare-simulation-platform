import signal
import time
from collections import defaultdict
from typing import Optional, Any

from src.consumer import KafkaConsumer
from src.writer import DeltaWriter
from src.config import BronzeIngestionConfig


class IngestionService:

    def __init__(self, batch_interval_seconds: int = 10):
        self.batch_interval_seconds = batch_interval_seconds
        self._running = True
        self._consumer: Optional[KafkaConsumer] = None
        self._writer: Optional[DeltaWriter] = None

        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        print(f"Received signal {signum}, shutting down gracefully...")
        self._running = False

    def _should_run(self) -> bool:
        return self._running

    def run(self) -> None:
        config = BronzeIngestionConfig.from_env()

        self._consumer = KafkaConsumer(
            bootstrap_servers=config.kafka_bootstrap_servers, group_id=config.kafka_group_id
        )
        self._writer = DeltaWriter(
            base_path=config.delta_base_path, storage_options=config.get_storage_options()
        )

        message_batches = defaultdict(list)
        last_write_time = time.time()

        while self._should_run():
            msg = self._consumer.poll(timeout=1.0)

            if msg is not None:
                topic = msg.topic()
                if topic is not None:
                    message_batches[topic].append(msg)

            current_time = time.time()
            if current_time - last_write_time >= self.batch_interval_seconds:
                all_messages = []

                for topic, messages in message_batches.items():
                    if messages:
                        try:
                            self._writer.write_batch(messages, topic=topic)
                            all_messages.extend(messages)
                        except Exception as e:
                            print(f"Error writing batch for {topic}: {e}")
                            raise

                if all_messages:
                    self._consumer.commit(messages=all_messages)

                message_batches.clear()
                last_write_time = current_time

        if message_batches:
            all_messages = []
            for topic, messages in message_batches.items():
                if messages:
                    self._writer.write_batch(messages, topic=topic)
                    all_messages.extend(messages)
            if all_messages:
                self._consumer.commit(messages=all_messages)

        if self._consumer:
            self._consumer.close()


def main() -> None:
    service = IngestionService()
    service.run()


if __name__ == "__main__":
    main()
