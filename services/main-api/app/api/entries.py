from typing import Optional
from uuid import UUID
from fastapi import Depends, APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import Response

from app.core.deps import get_current_user_id
from app.models import Entry
from app.repositories.entry_repository import EntryRepository
from app.schemas.entry import EntryRead, EntryCreate, EntryUpdate
from app.services.entry_service import EntryService
from app.db.db_engine import get_async_session

router = APIRouter()


def get_entry_service(
    session: AsyncSession = Depends(get_async_session),
) -> EntryService:
    return EntryService(EntryRepository(session))


@router.get("/", response_model=list[EntryRead], status_code=status.HTTP_200_OK)
async def get_all_entry(
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> list[Entry]:
    return await service.get_all_entries(owner_id)


@router.get("/{entry_id}", response_model=EntryRead, status_code=status.HTTP_200_OK)
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


@router.post("/", response_model=EntryCreate, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: EntryCreate,
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> Entry:
    return await service.create_entry(body, owner_id)


@router.put("/{entry_id}", response_model=EntryRead, status_code=status.HTTP_200_OK)
async def update_entry(
    entry_id: UUID,
    body: EntryUpdate,
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> Entry:
    return await service.update_entry(body, owner_id, entry_id)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: UUID,
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> Response:
    await service.delete_entry(entry_id, owner_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
