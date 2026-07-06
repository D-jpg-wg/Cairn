import json
import uuid

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import setting
from app.db.db_engine import async_session
from app.kafka.messaging import publish_event
from app.models import Entry, Subscription, Tag
from app.models.entry import EntryStatus, EntryType, entry_tags
from app.schemas.entry import _normalize_tags


async def _get_or_create_tag_ids(
    session: AsyncSession, names: list[str]
) -> list[uuid.UUID]:
    """Создаёт недостающие теги и возвращает id всех запрошенных."""
    if not names:
        return []
    await session.execute(
        pg_insert(Tag)
        .values([{"name": n} for n in names])
        .on_conflict_do_nothing(index_elements=["name"])
    )
    result = await session.execute(select(Tag.id).where(Tag.name.in_(names)))
    return list(result.scalars())


async def _handle_page(event: dict) -> None:
    """Раздаёт спарсенную страницу подписчикам её ленты; дубли гасит индекс."""
    async with async_session() as session:
        result = await session.execute(
            select(Subscription.user_id).where(
                Subscription.feed_url == event["source_url"]
            )
        )
        inserted: list[tuple[uuid.UUID, uuid.UUID]] = []
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
                inserted.append((entry_id, user_id))

        tag_ids = await _get_or_create_tag_ids(
            session, _normalize_tags(event.get("tags", []))
        )
        if inserted and tag_ids:
            await session.execute(
                pg_insert(entry_tags).values(
                    [
                        {"entry_id": entry_id, "tag_id": tag_id}
                        for entry_id, _ in inserted
                        for tag_id in tag_ids
                    ]
                )
            )
        await session.commit()

    for entry_id, owner_id in inserted:
        await publish_event(
            "entry.created",
            key=str(entry_id),
            value={
                "id": str(entry_id),
                "owner_id": str(owner_id),
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
