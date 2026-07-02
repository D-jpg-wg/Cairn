from typing import Optional
from uuid import UUID

from app.models import Entry, Tag
from app.models.entry import ENRICHABLE_TYPES
from app.worker.tasks import enrich_entry
from app.repositories.entry_repository import EntryRepository
from app.schemas.entry import EntryCreate, EntryUpdate
from app.kafka.messaging import publish_event


class EntryService:
    """Бизнес-логика записей: операции всегда в рамках owner_id пользователя."""

    def __init__(self, repo: EntryRepository) -> None:
        self.repo = repo

    async def get_all_entries(
        self,
        owner_id: UUID,
        tag: Optional[list[str]] = None,
        q: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Entry]:
        """Записи пользователя с опциональным фильтром по тегу и поиском по тексту."""
        return await self.repo.get_all_entries(owner_id, tag, q, limit, offset)

    async def get_entry(self, entry_id: UUID, owner_id: UUID) -> Optional[Entry]:
        """Одна запись пользователя по id (или None)."""
        return await self.repo.get_by_id(entry_id, owner_id)

    async def create_entry(self, body: EntryCreate, owner_id: UUID) -> Entry:
        """Создаёт запись; для url-типов планирует фоновое обогащение."""
        entry = await self.repo.create_entry(body, owner_id)
        if entry.type in ENRICHABLE_TYPES:
            enrich_entry.delay(str(entry.id))
        await publish_event(
            "entry.created",
            key=str(entry.id),
            value={
                "id": str(entry.id),
                "owner_id": str(entry.owner_id),
                "type": entry.type.value,
                "url": entry.url,
            },
        )
        return entry

    async def update_entry(
        self, body: EntryUpdate, owner_id: UUID, entry_id: UUID
    ) -> Optional[Entry]:
        """Обновляет запись пользователя (или None, если не найдена)."""
        return await self.repo.update_entry(entry_id, body, owner_id)

    async def delete_entry(self, entry_id: UUID, owner_id: UUID) -> Optional[Entry]:
        """Удаляет запись пользователя (или None, если не найдена)."""
        return await self.repo.delete_entry(entry_id, owner_id)

    async def get_tags(self, owner_id: UUID) -> list[Tag]:
        """Все теги пользователя."""
        return await self.repo.get_tags(owner_id)
