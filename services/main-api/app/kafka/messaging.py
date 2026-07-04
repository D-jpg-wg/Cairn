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
    """Кладёт событие в батч продюсера, не дожидаясь ack брокера.

    Размен: запрос не платит ~20 мс за подтверждение, но при падении брокера
    событие может потеряться — ошибка доставки всплывёт только в логах.
    """
    if _producer is None:
        raise RuntimeError("Kafka producer not started.")
    await _producer.send(
        topic,
        key=key.encode(),
        value=json.dumps(value).encode(),
    )
