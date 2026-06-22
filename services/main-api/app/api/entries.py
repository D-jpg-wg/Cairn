from typing import Optional
from uuid import UUID
from fastapi import Depends, APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.deps import get_current_user_id
from app.models import Entry
from app.repositories.entry_repository import EntryRepository
from app.schemas.entry import EntryRead
from app.services.entry_service import EntryService
from app.db.db_engine import get_async_session

router = APIRouter()


def get_entry_service(
    session: AsyncSession = Depends(get_async_session),
) -> EntryService:
    return EntryService(EntryRepository(session))


@router.get("/", response_model=list[EntryRead])
async def get_all_entry(
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> list[Entry]:
    return await service.get_all_entries(owner_id)


@router.get("/{entry_id}", response_model=EntryRead)
async def get_entry(
    entry_id: UUID,
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> Optional[Entry]:
    result = await service.get_entry(entry_id=entry_id, owner_id=owner_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
        )
    return result
