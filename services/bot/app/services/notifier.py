import asyncio
import contextlib
import json
import uuid

from aiogram import Bot
from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import texts
from app.core.config import setting
from app.repositories.bot_repository import BotRepository

TYPE_ICON = {"link": "🔗", "article": "📰", "video": "🎬", "note": "📝", "snippet": "✂️"}
DIGEST_WINDOW_SECONDS = 60.0


class ArticleDigest:
    """Копит статьи одного чата и шлёт их одним сообщением раз в окно.

    Таймер стартует от ПЕРВОЙ статьи окна (не скользящий): при непрерывном
    потоке чат всё равно получит дайджест не реже раза в window_seconds,
    а не будет ждать затишья бесконечно.
    """

    def __init__(self, bot: Bot, window_seconds: float = DIGEST_WINDOW_SECONDS) -> None:
        self._bot = bot
        self._window_seconds = window_seconds
        self._pending: dict[int, list[dict]] = {}
        self._tasks: dict[int, asyncio.Task] = {}

    def add(self, telegram_id: int, title: str, url: str | None) -> None:
        self._pending.setdefault(telegram_id, []).append({"title": title, "url": url})
        if telegram_id not in self._tasks:
            self._tasks[telegram_id] = asyncio.create_task(
                self._flush_after_delay(telegram_id)
            )

    async def _flush_after_delay(self, telegram_id: int) -> None:
        await asyncio.sleep(self._window_seconds)
        await self._flush(telegram_id)

    async def _flush(self, telegram_id: int) -> None:
        items = self._pending.pop(telegram_id, [])
        self._tasks.pop(telegram_id, None)
        if not items:
            return
        lines = "\n".join(
            f"• {i['title']}" + (f"\n  {i['url']}" if i["url"] else "") for i in items
        )
        text = f"{texts.ARTICLE_DIGEST_HEADER.format(n=len(items))}\n{lines}"
        try:
            await self._bot.send_message(telegram_id, text)
        except Exception:
            pass

    async def aclose(self) -> None:
        """Гасит ожидающие таймеры и шлёт то, что успело накопиться (остановка бота)."""
        pending_ids = list(self._tasks)
        for telegram_id in pending_ids:
            self._tasks[telegram_id].cancel()
        for telegram_id in pending_ids:
            with contextlib.suppress(asyncio.CancelledError):
                await self._tasks[telegram_id]
            await self._flush(telegram_id)


async def _handle_entry_created(
    event: dict,
    session_factory: async_sessionmaker[AsyncSession],
    bot: Bot,
    digest: ArticleDigest,
) -> None:
    """Один owner_id — одна привязка; статьи копятся в digest, остальное шлётся сразу."""
    async with session_factory() as session:
        link = await BotRepository(session).get_by_user_id(uuid.UUID(event["owner_id"]))
    if link is None:
        return

    if event["type"] == "article":
        digest.add(
            link.telegram_id, event.get("title") or "Без названия", event.get("url")
        )
        return

    icon = TYPE_ICON.get(event["type"], "•")
    text = f"{icon} {texts.NEW_ENTRY}"
    if event.get("url"):
        text += f"\n{event['url']}"
    try:
        await bot.send_message(link.telegram_id, text)
    except Exception:
        pass


async def run_notifier(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    digest_window_seconds: float = DIGEST_WINDOW_SECONDS,
) -> None:
    """Слушает entry.created и шлёт уведомление владельцу, если он привязал Telegram.
    Отдельная группа bot-notifier: Kafka раздаёт каждой группе полную копию
    потока, search-indexer нам не конкурент.

    Статьи (type=article) не шлются мгновенно — их за один прогон парсера
    может прийти десятки, поэтому они копятся в ArticleDigest и уходят одним
    сообщением. Остальные типы (личные записи) — как раньше, сразу.
    """
    consumer = AIOKafkaConsumer(
        "entry.created",
        bootstrap_servers=setting.kafka_bootstrap_servers,
        group_id="bot-notifier",
    )
    await consumer.start()
    digest = ArticleDigest(bot, digest_window_seconds)
    try:
        async for msg in consumer:
            await _handle_entry_created(
                json.loads(msg.value), session_factory, bot, digest
            )
    finally:
        await digest.aclose()
        await consumer.stop()
