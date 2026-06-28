import json
from collections.abc import AsyncIterator
from uuid import UUID

import redis
import redis.asyncio as aioredis

from app.core.config import setting

# Персональный канал на пользователя: подписчик получает только свои события.
_CHANNEL_PREFIX = "entries:events"

# Sync-клиент для воркера (Celery sync). Async-клиент создаётся на каждое SSE-соединение.
_publisher = redis.Redis.from_url(setting.celery_broker_url)


def channel_for(owner_id: UUID) -> str:
    return f"{_CHANNEL_PREFIX}/{owner_id}"


def publish_status(owner_id: UUID, entry_id: UUID, status: str) -> None:
    """Уведомление о смене статуса записи в канал юзера. Вызывается из Celery-воркера (sync)."""
    _publisher.publish(
        channel_for(owner_id),
        json.dumps({"id": str(entry_id), "status": status}),
    )


async def subscribe_status(owner_id: UUID) -> AsyncIterator[str | None]:
    """Подписка на события юзера для SSE.

    Yield-ит JSON-payload события, либо None как «тик» (за интервал событий не было) —
    эндпоинт превращает тик в SSE-heartbeat. Соединение к Redis живёт на время подписки и
    закрывается в finally, когда потребитель прекращает итерацию (клиент отключился).
    """
    client = aioredis.from_url(setting.celery_broker_url)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel_for(owner_id))
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
            yield msg["data"].decode() if msg else None
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()
        await client.aclose()
