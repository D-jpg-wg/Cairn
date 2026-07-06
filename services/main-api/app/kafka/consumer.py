import json
from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import setting
from app.db.db_engine import async_session
from app.kafka.messaging import publish_event
from app.models import Entry, Subscription
from app.models.entry import EntryStatus, EntryType


async def _handle_page(event: dict) -> None:
    """Раздаёт спарсенную страницу подписчикам её ленты; дубли гасит индекс."""
    async with async_session() as session:
        result = await session.execute(
            select(Subscription.user_id).where(
                Subscription.feed_url == event["source_url"]
            )
        )
        inserted: list[tuple[str, str]] = []
        for user_id in result.scalars():
            stmt = (
                pg_insert(Entry)
                .values(
                    owner_id=user_id,
                    type=EntryType.ARTICLE,
                    status=EntryStatus.READY,
                    title=event["title"][:255],
                    content=event["summary"],
                    url=event["url"],
                )
                .on_conflict_do_nothing()
                .returning(Entry.id)
            )
            entry_id = (await session.execute(stmt)).scalar()
            if entry_id is not None:
                inserted.append((str(entry_id), str(user_id)))
        await session.commit()

    for entry_id, owner_id in inserted:
        await publish_event(
            "entry.created",
            key=entry_id,
            value={
                "id": entry_id,
                "owner_id": owner_id,
                "type": EntryType.ARTICLE.value,
                "url": event["url"],
            },
        )


async def run_page_consumer() -> None:
    consumer = AIOKafkaConsumer(
        "page.parsed",
        bootstrap_servers=setting.kafka_bootstrap_servers,
        group_id="main-api",
        auto_offset_reset="earliest",
    )
    await consumer.start()

    try:
        async for msg in consumer:
            try:
                await _handle_page(json.loads(msg.value))
            except Exception as exc:  # noqa: BLE001 — ядовитое событие не должно убить консьюмер
                print(f"[page.parsed] ошибка обработки: {exc!r}", flush=True)
    finally:
        await consumer.stop()
