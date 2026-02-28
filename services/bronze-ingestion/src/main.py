import signal
import time
from collections import defaultdict
from typing import Optional, Any

from src.consumer import KafkaConsumer
from src.writer import DeltaWriter
from src.dlq_writer import DLQWriter, DLQRecord
from src.schema_validator import SchemaValidator
from src.config import BronzeIngestionConfig
from src.health import start_health_server, health_state


class IngestionService:

    def __init__(self, batch_interval_seconds: int = 10):
        self.batch_interval_seconds = batch_interval_seconds
        self._running = True
        self._consumer: Optional[KafkaConsumer] = None
        self._writer: Optional[DeltaWriter] = None
        self._dlq_writer: Optional[DLQWriter] = None
        self._schema_validator: Optional[SchemaValidator] = None

        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        print(f"Received signal {signum}, shutting down gracefully...")
        self._running = False

    def _should_run(self) -> bool:
        return self._running

    def _process_batch(
        self,
        message_batches: defaultdict[str, list[Any]],
        dlq_batch: list[DLQRecord],
    ) -> None:
        """Write valid messages to Bronze and DLQ records to DLQ tables."""
        all_messages: list[Any] = []

        for topic, messages in message_batches.items():
            if messages:
                try:
                    assert self._writer is not None
                    self._writer.write_batch(messages, topic=topic)
                    all_messages.extend(messages)
                except Exception as e:
                    health_state.record_error()
                    print(f"Error writing batch for {topic}: {e}")
                    raise

        if dlq_batch and self._dlq_writer is not None:
            try:
                self._dlq_writer.write_batch(dlq_batch)
                health_state.record_dlq_write(len(dlq_batch))
                print(f"Wrote {len(dlq_batch)} messages to DLQ")
            except Exception as e:
                health_state.record_error()
                print(f"Error writing DLQ batch: {e}")

        if all_messages:
            health_state.record_write(len(all_messages))

        assert self._consumer is not None
        if all_messages or dlq_batch:
            self._consumer.commit(messages=all_messages or None)

    def run(self) -> None:
        config = BronzeIngestionConfig.from_env()

        start_health_server(port=8080)

        self._consumer = KafkaConsumer(
            bootstrap_servers=config.kafka_bootstrap_servers,
            group_id=config.kafka_group_id,
            security_protocol=config.kafka_security_protocol,
            sasl_mechanism=config.kafka_sasl_mechanism,
            sasl_username=config.kafka_sasl_username,
            sasl_password=config.kafka_sasl_password,
        )
        self._writer = DeltaWriter(
            base_path=config.delta_base_path, storage_options=config.get_storage_options()
        )

        self._writer.initialize_tables(KafkaConsumer.TOPICS)
        print(f"Initialized {len(KafkaConsumer.TOPICS)} bronze Delta tables")

        if config.dlq.enabled:
            self._dlq_writer = DLQWriter(
                base_path=config.delta_base_path,
                storage_options=config.get_storage_options(),
            )
            self._dlq_writer.initialize_tables(KafkaConsumer.TOPICS)
            print(f"Initialized {len(KafkaConsumer.TOPICS)} DLQ Delta tables")
            if config.dlq.validate_schema:
                self._schema_validator = SchemaValidator(config.dlq.schema_dir)
                print(f"Schema validation enabled (schema_dir={config.dlq.schema_dir})")
            print(f"DLQ routing enabled (validate_json={config.dlq.validate_json})")

        message_batches: defaultdict[str, list[Any]] = defaultdict(list)
        dlq_batch: list[DLQRecord] = []
        last_write_time = time.time()

        while self._should_run():
            msg = self._consumer.poll(timeout=1.0)

            if msg is not None:
                topic = msg.topic()

                if config.dlq.enabled:
                    error_type, error_message = self._consumer.validate_message(
                        msg,
                        validate_json=config.dlq.validate_json,
                        schema_validator=self._schema_validator,
                    )
                    if error_type is not None and error_message is not None:
                        dlq_record = self._consumer.build_dlq_record(msg, error_type, error_message)
                        dlq_batch.append(dlq_record)
                        continue

                if topic is not None:
                    message_batches[topic].append(msg)

            current_time = time.time()
            if current_time - last_write_time >= self.batch_interval_seconds:
                self._process_batch(message_batches, dlq_batch)
                message_batches.clear()
                dlq_batch.clear()
                last_write_time = current_time

        # Flush remaining messages on shutdown
        if message_batches or dlq_batch:
            self._process_batch(message_batches, dlq_batch)

        if self._consumer:
            self._consumer.close()


def main() -> None:
    service = IngestionService()
    service.run()


if __name__ == "__main__":
    main()
