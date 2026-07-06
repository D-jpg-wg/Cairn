from fastapi import Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.repositories.subscription_repository import SubscriptionRepository
from app.services.subscription_service import SubscriptionService
from app.db.db_engine import get_async_session

router = APIRouter()


def get_subscription_service(
    session: AsyncSession = Depends(get_async_session),
) -> SubscriptionService:
    """Зависимость: собирает SubscriptionService поверх сессии БД."""
    return SubscriptionService(SubscriptionRepository(session))


@router.get("/feeds", response_model=list[str], status_code=status.HTTP_200_OK)
async def get_all_feeds(
    service: SubscriptionService = Depends(get_subscription_service),
) -> list[str]:
    """Ленты, на которые хоть кто-то подписан — читает парсер, без авторизации:
    он не знает про юзеров (database-per-service), ему нужен только список URL."""
    return await service.get_all_feed_urls()
