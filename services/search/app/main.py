import asyncio
import json
import app.grpc_gen  # noqa: F401

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.grpc_server import serve as serve_grpc


async def consume() -> None:
    consumer = AIOKafkaConsumer(
        "entry.created",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="search-indexer",
        auto_offset_reset="earliest",
    )
    await consumer.start()
    print("[search] слушаю entry.created...", flush=True)
    try:
        async for msg in consumer:
            event = json.loads(msg.value)
            print(f"[search] entry.created: {event} - would index", flush=True)

    finally:
        await consumer.stop()


async def main() -> None:
    await asyncio.gather(consume(), serve_grpc())


if __name__ == "__main__":
    asyncio.run(main())
