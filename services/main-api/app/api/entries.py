from typing import Optional
from uuid import UUID

from fastapi import Depends, APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from app.events import subscribe_status
from app.core.deps import get_current_user_id
from app.grpc_client import search_entries
from app.models import Entry, Tag
from app.repositories.entry_repository import EntryRepository
from app.schemas.entry import EntryRead, EntryCreate, EntryUpdate, TagRead
from app.services.entry_service import EntryService
from app.db.db_engine import get_async_session
from app.validations.check_exists import check_exists_entry

router = APIRouter()


def get_entry_service(
    session: AsyncSession = Depends(get_async_session),
) -> EntryService:
    """Зависимость: собирает EntryService поверх сессии БД."""
    return EntryService(EntryRepository(session))


@router.get("/tags", response_model=list[TagRead], status_code=status.HTTP_200_OK)
async def get_all_tags(
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> list[Tag]:
    """Возвращает все теги текущего пользователя."""
    tags = await service.get_tags(owner_id)
    return tags


@router.get("/stream")
async def stream_entries(
    request: Request,
    owner_id: UUID = Depends(get_current_user_id),
) -> StreamingResponse:
    """Long-lived SSE: пушит {id, status} при смене статуса записей юзера."""

    async def event_gen():
        # Транспорт (Redis) живёт в app.events; здесь — только SSE-обёртка.
        async for data in subscribe_status(owner_id):
            if await request.is_disconnected():
                break
            # data is None — тик без событий, шлём heartbeat-комментарий, чтобы прокси
            # не рвал «немое» соединение.
            yield ": keep-alive\n\n" if data is None else f"data: {data}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # отключить буферизацию у nginx
        },
    )


@router.get("/search")
async def semantic_search(
    q: str,
    owner_id: UUID = Depends(get_current_user_id),
) -> dict:
    """Семантический поиск: спрашивает search-сервис по gRPC, возвращает id похожих."""
    ids = await search_entries(owner_id=str(owner_id), query=q, limit=10)
    return {"query": q, "entry_ids": ids}


@router.get("/", response_model=list[EntryRead], status_code=status.HTTP_200_OK)
async def get_all_entry(
    q: str | None = None,
    tag: list[str] | None = Query(None),
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> list[Entry]:
    """Список записей пользователя с фильтром по тегу и поиском по тексту."""
    return await service.get_all_entries(owner_id, tag, q)


@router.get("/{entry_id}", response_model=EntryRead, status_code=status.HTTP_200_OK)
async def get_entry(
    entry_id: UUID,
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> Optional[Entry]:
    """Возвращает одну запись пользователя по id; 404, если не найдена."""
    result = await service.get_entry(entry_id=entry_id, owner_id=owner_id)
    result = check_exists_entry(result)
    return result


@router.post("/", response_model=EntryRead, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: EntryCreate,
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> Entry:
    """Создаёт запись для текущего пользователя."""
    return await service.create_entry(body, owner_id)


@router.patch("/{entry_id}", response_model=EntryRead, status_code=status.HTTP_200_OK)
async def update_entry(
    entry_id: UUID,
    body: EntryUpdate,
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> Entry:
    """Частично обновляет запись пользователя; 404, если не найдена."""
    result = await service.update_entry(body, owner_id, entry_id)
    result = check_exists_entry(result)
    return result


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: UUID,
    service: EntryService = Depends(get_entry_service),
    owner_id: UUID = Depends(get_current_user_id),
) -> Response:
    """Удаляет запись пользователя; 404, если не найдена."""
    deleted = await service.delete_entry(entry_id, owner_id)
    check_exists_entry(deleted)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
