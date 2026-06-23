from typing import Optional
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Entry, Tag
from app.schemas.entry import EntryCreate, EntryUpdate


class EntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_or_create_tags(self, names: list[str]) -> list[Tag]:
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
        stmt = await self.session.execute(
            select(Entry)
            .where(Entry.id == entry_id, Entry.owner_id == owner_id)
            .options(selectinload(Entry.tags))
        )
        return stmt.scalars().first()

    async def get_all_entries(
        self,
        owner_id: UUID,
        tag: Optional[str] = None,
        q: Optional[str] = None,
    ) -> list[Entry]:
        stmt = (
            select(Entry)
            .where(Entry.owner_id == owner_id)
            .options(selectinload(Entry.tags))
            .order_by(Entry.created_at.desc())
        )
        if tag is not None:
            stmt = stmt.join(Entry.tags).where(Tag.name == tag.lower().strip())
        if q is not None:
            stmt = stmt.where(
                or_(Entry.title.ilike(f"%{q}%"), Entry.content.ilike(f"%{q}%"))
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_entry(self, body: EntryCreate, owner_id: UUID) -> Entry:
        data = body.model_dump()
        tags = data.pop("tags", [])
        entry = Entry(owner_id=owner_id, **data)
        entry.tags = await self._get_or_create_tags(tags)
        self.session.add(entry)
        await self.session.commit()
        created = await self.get_by_id(entry.id, owner_id)
        assert created is not None
        return created

    async def update_entry(
        self, entry_id: UUID, entry: EntryUpdate, owner_id: UUID
    ) -> Optional[Entry]:
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
        entry = await self.get_by_id(entry_id, owner_id)
        if entry is None:
            return None
        await self.session.delete(entry)
        await self.session.commit()
        return entry

    async def get_tags(self, owner_id: UUID) -> list[Tag]:
        tags = await self.session.execute(
            select(Tag).join(Tag.entries).where(Entry.owner_id == owner_id).distinct()
        )
        return list(tags.scalars().all())
