from typing import Optional
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Entry, Tag
from app.models.entry import ENRICHABLE_TYPES, EntryStatus
from app.schemas.entry import EntryCreate, EntryUpdate


class EntryRepository:
    """Доступ к записям и тегам в БД."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_or_create_tags(self, names: list[str]) -> list[Tag]:
        """Возвращает существующие теги по именам, недостающие создаёт (без дублей)."""
        if not names:
            return []
        unique = list(dict.fromkeys(names))  # дедуп, сохраняя порядок
        existing = await self.session.execute(select(Tag).where(Tag.name.in_(unique)))
        by_name = {tag.name: tag for tag in existing.scalars().all()}
        for name in unique:
            if name not in by_name:
                by_name[name] = Tag(name=name)
        return [by_name[name] for name in unique]

    async def get_by_id(self, entry_id: UUID, owner_id: UUID) -> Optional[Entry]:
        """Запись по id в пределах владельца, с подгруженными тегами (или None)."""
        stmt = await self.session.execute(
            select(Entry)
            .where(Entry.id == entry_id, Entry.owner_id == owner_id)
            .options(selectinload(Entry.tags))
        )
        return stmt.scalars().first()

    async def get_all_entries(
        self,
        owner_id: UUID,
        tag: Optional[list[str]] = None,
        q: Optional[str] = None,
    ) -> list[Entry]:
        """Записи владельца (новые сверху). tag фильтрует по ЛЮБОМУ из тегов (OR),
        q ищет подстроку в title/content."""
        stmt = (
            select(Entry)
            .where(Entry.owner_id == owner_id)
            .options(selectinload(Entry.tags))
            .order_by(Entry.created_at.desc())
        )
        if tag:
            names = [t.lower().strip() for t in tag if t.strip()]
            if names:
                # Запись попадает в выборку, если у неё есть хотя бы один из тегов.
                # distinct — чтобы join не задвоил запись с несколькими совпадениями.
                stmt = stmt.join(Entry.tags).where(Tag.name.in_(names)).distinct()
        if q is not None:
            stmt = stmt.where(
                or_(Entry.title.ilike(f"%{q}%"), Entry.content.ilike(f"%{q}%"))
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_entry(self, body: EntryCreate, owner_id: UUID) -> Entry:
        """Создаёт запись владельца, привязывает теги и возвращает её с тегами."""
        data = body.model_dump()
        tags = data.pop("tags", [])
        status = (
            EntryStatus.PENDING if body.type in ENRICHABLE_TYPES else EntryStatus.READY
        )
        entry = Entry(owner_id=owner_id, status=status, **data)
        entry.tags = await self._get_or_create_tags(tags)
        self.session.add(entry)
        await self.session.commit()
        created = await self.get_by_id(entry.id, owner_id)
        assert created is not None
        return created

    async def update_entry(
        self, entry_id: UUID, entry: EntryUpdate, owner_id: UUID
    ) -> Optional[Entry]:
        """Обновляет только переданные поля записи владельца; теги заменяет, если заданы."""
        old_entry = await self.get_by_id(entry_id, owner_id)
        if old_entry is None:
            return None
        data = entry.model_dump(exclude_unset=True)
        tags = data.pop("tags", None)
        for field, value in data.items():
            setattr(old_entry, field, value)
        if tags is not None:
            old_entry.tags = await self._get_or_create_tags(tags)
        await self.session.commit()
        await self.session.refresh(old_entry, attribute_names=["tags"])
        return old_entry

    async def delete_entry(self, entry_id: UUID, owner_id: UUID) -> Optional[Entry]:
        """Удаляет запись владельца и возвращает её (или None, если не найдена)."""
        entry = await self.get_by_id(entry_id, owner_id)
        if entry is None:
            return None
        await self.session.delete(entry)
        await self.session.commit()
        return entry

    async def get_tags(self, owner_id: UUID) -> list[Tag]:
        """Уникальные теги, встречающиеся в записях владельца."""
        tags = await self.session.execute(
            select(Tag).join(Tag.entries).where(Entry.owner_id == owner_id).distinct()
        )
        return list(tags.scalars().all())
