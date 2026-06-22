from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entry


class EntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entry_id: UUID, owner_id: UUID) -> Optional[Entry]:
        stmt = await self.session.execute(
            select(Entry).where(Entry.id == entry_id, Entry.owner_id == owner_id)
        )
        return stmt.scalars().first()

    async def get_all_entries(self, owner_id: UUID) -> list[Entry]:
        stmt = await self.session.execute(
            select(Entry).where(Entry.owner_id == owner_id)
        )
        return list(stmt.scalars().all())

    async def create_entry(self, entry: Entry, owner_id: UUID) -> Entry:
        pass

    async def update_entry(self, entry_id: UUID, entry: Entry, owner_id: UUID) -> Entry:
        pass

    async def delete_entry(self, entry_id: UUID, owner_id: UUID) -> Entry:
        pass
