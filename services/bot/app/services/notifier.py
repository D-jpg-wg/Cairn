import json
import uuid

from aiogram import Bot
from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import texts
from app.core.config import setting
from app.repositories.bot_repository import BotRepository

TYPE_ICON = {"link": "🔗", "article": "📰", "video": "🎬", "note": "📝", "snippet": "✂️"}


async def run_notifier(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Слушает entry.created и шлёт уведомление владельцу, если он привязал Telegram.
    Отдельная группа bot-notifier: Kafka раздаёт каждой группе полную копию
    потока, search-indexer нам не конкурент.
    """
    consumer = AIOKafkaConsumer(
        "entry.created",
        bootstrap_servers=setting.kafka_bootstrap_servers,
        group_id="bot-notifier",
    )
    await consumer.start()
    try:
        async for msg in consumer:
            event = json.loads(msg.value)

            async with session_factory() as session:
                link = await BotRepository(session).get_by_user_id(
                    uuid.UUID(event["owner_id"])
                )
                if link is None:
                    continue

            icon = TYPE_ICON.get(event["type"], "•")
            text = f"{icon} {texts.NEW_ENTRY}"
            if event.get("url"):
                text += f"\n{event['url']}"
            try:
                await bot.send_message(
                    link.telegram_id,
                    text,
                )
            except Exception:
                pass
    finally:
        await consumer.stop()
