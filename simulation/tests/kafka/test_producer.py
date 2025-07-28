from unittest.mock import Mock, patch

from kafka.producer import KafkaProducer


class TestKafkaProducer:
    def test_producer_init(self):
        config = {"bootstrap.servers": "localhost:9092", "client.id": "test-producer"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            KafkaProducer(config)

            mock_producer_class.assert_called_once()
            call_config = mock_producer_class.call_args[0][0]
            assert call_config["bootstrap.servers"] == "localhost:9092"
            assert call_config["client.id"] == "test-producer"

    def test_producer_produce_success(self):
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)
            callback = Mock()

            producer.produce("test-topic", key="key1", value="value1", callback=callback)

            mock_producer_instance.produce.assert_called_once_with(
                "test-topic", key="key1", value="value1", on_delivery=callback
            )
            mock_producer_instance.poll.assert_called_once_with(0)

    def test_producer_produce_error_callback(self):
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            error_callback = Mock()
            producer = KafkaProducer(config)

            def trigger_error_callback(*args, **kwargs):
                on_delivery = kwargs.get("on_delivery")
                if on_delivery:
                    mock_err = Mock()
                    mock_msg = Mock()
                    on_delivery(mock_err, mock_msg)

            mock_producer_instance.produce.side_effect = trigger_error_callback

            producer.produce("test-topic", key="key1", value="value1", callback=error_callback)

            error_callback.assert_called_once()
            assert error_callback.call_args[0][0] is not None

    def test_producer_flush_on_shutdown(self):
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)
            producer.close()

            mock_producer_instance.flush.assert_called_once()

    def test_producer_config_acks_all(self):
        config = {"bootstrap.servers": "localhost:9092", "client.id": "test-producer"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            KafkaProducer(config)

            call_config = mock_producer_class.call_args[0][0]
            assert call_config["acks"] == "all"

    def test_producer_async_produce(self):
        config = {"bootstrap.servers": "localhost:9092"}

        with patch("kafka.producer.Producer") as mock_producer_class:
            mock_producer_instance = Mock()
            mock_producer_class.return_value = mock_producer_instance

            producer = KafkaProducer(config)

            producer.produce("test-topic", key="key1", value="value1")
            producer.produce("test-topic", key="key2", value="value2")
            producer.produce("test-topic", key="key3", value="value3")

            assert mock_producer_instance.produce.call_count == 3
            assert mock_producer_instance.poll.call_count == 3

            for call_args in mock_producer_instance.poll.call_args_list:
                assert call_args[0][0] == 0
