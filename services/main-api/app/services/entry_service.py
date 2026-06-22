from typing import Optional
from uuid import UUID

from app.models import Entry
from app.repositories.entry_repository import EntryRepository
from app.schemas.entry import EntryCreate, EntryUpdate


class EntryService:
    def __init__(self, repo: EntryRepository) -> None:
        self.repo = repo

    async def get_all_entries(self, owner_id: UUID) -> list[Entry]:
        return await self.repo.get_all_entries(owner_id)

    async def get_entry(self, entry_id: UUID, owner_id: UUID) -> Optional[Entry]:
        return await self.repo.get_by_id(entry_id, owner_id)

    async def create_entry(self, body: EntryCreate, owner_id: UUID) -> Entry:
        pass

    async def update_entry(
        self, body: EntryUpdate, owner_id: UUID, entry_id: UUID
    ) -> Entry:
        pass

    async def delete_entry(self, entry_id: UUID, owner_id: UUID) -> Entry:
        pass
