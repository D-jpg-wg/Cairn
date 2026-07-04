import json

from aiokafka import AIOKafkaProducer

from app.core.config import setting


_producer: AIOKafkaProducer | None = None


async def start_producer() -> None:
    global _producer
    _producer = AIOKafkaProducer(bootstrap_servers=setting.kafka_bootstrap_servers)
    await _producer.start()


async def stop_producer() -> None:
    if _producer is not None:
        await _producer.stop()


async def publish_event(topic: str, key: str, value: dict) -> None:
    """Шлёт событие в топик и ждёт подтверждения брокера (send_and_wait)."""
    if _producer is None:
        raise RuntimeError("Kafka producer not started.")
    await _producer.send(
        topic,
        key=key.encode(),
        value=json.dumps(value).encode(),
    )
