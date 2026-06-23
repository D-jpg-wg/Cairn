from typing import Optional
from uuid import UUID

from app.models import Entry, Tag
from app.repositories.entry_repository import EntryRepository
from app.schemas.entry import EntryCreate, EntryUpdate


class EntryService:
    def __init__(self, repo: EntryRepository) -> None:
        self.repo = repo

    async def get_all_entries(
        self, owner_id: UUID, tag: Optional[str] = None
    ) -> list[Entry]:
        return await self.repo.get_all_entries(owner_id, tag)

    async def get_entry(self, entry_id: UUID, owner_id: UUID) -> Optional[Entry]:
        return await self.repo.get_by_id(entry_id, owner_id)

    async def create_entry(self, body: EntryCreate, owner_id: UUID) -> Entry:
        return await self.repo.create_entry(body, owner_id)

    async def update_entry(
        self, body: EntryUpdate, owner_id: UUID, entry_id: UUID
    ) -> Optional[Entry]:
        return await self.repo.update_entry(entry_id, body, owner_id)

    async def delete_entry(self, entry_id: UUID, owner_id: UUID) -> Optional[Entry]:
        return await self.repo.delete_entry(entry_id, owner_id)

    async def get_tags(self, owner_id: UUID) -> list[Tag]:
        return await self.repo.get_tags(owner_id)
