import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from prometheus_client import Counter, Histogram

updates_total = Counter(
    "bot_updates_total", "Обработанные апдейты бота", ["event_type", "status"]
)
update_duration_seconds = Histogram(
    "bot_update_duration_seconds", "Длительность обработки апдейта бота", ["event_type"]
)


class MetricsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        event_type = event.__class__.__name__
        start = time.monotonic()
        status = "ok"
        try:
            return await handler(event, data)
        except Exception:
            status = "error"
            raise
        finally:
            update_duration_seconds.labels(event_type=event_type).observe(
                time.monotonic() - start
            )
            updates_total.labels(event_type=event_type, status=status).inc()
