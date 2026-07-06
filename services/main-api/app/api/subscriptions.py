from uuid import UUID

from fastapi import Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import Response

from app.core.deps import get_current_user_id
from app.models import Subscription
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import SubscriptionRead, SubscriptionCreate
from app.services.subscription_service import SubscriptionService
from app.db.db_engine import get_async_session
from app.validations.check_exists import check_exists_subscription

router = APIRouter()


def get_subscription_service(
    session: AsyncSession = Depends(get_async_session),
) -> SubscriptionService:
    """Зависимость: собирает SubscriptionService поверх сессии БД."""
    return SubscriptionService(SubscriptionRepository(session))


@router.get("/", response_model=list[SubscriptionRead], status_code=status.HTTP_200_OK)
async def get_all_subscriptions(
    service: SubscriptionService = Depends(get_subscription_service),
    user_id: UUID = Depends(get_current_user_id),
) -> list[Subscription]:
    """Подписки текущего пользователя."""
    return await service.get_all(user_id)


@router.post("/", response_model=SubscriptionRead, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: SubscriptionCreate,
    service: SubscriptionService = Depends(get_subscription_service),
    user_id: UUID = Depends(get_current_user_id),
) -> Subscription:
    """Подписывает пользователя на ленту (повторная подписка — no-op)."""
    return await service.create(user_id, body.feed_url)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: UUID,
    service: SubscriptionService = Depends(get_subscription_service),
    user_id: UUID = Depends(get_current_user_id),
) -> Response:
    """Отписывает пользователя от ленты; 404, если подписки не было."""
    deleted = await service.delete(subscription_id, user_id)
    check_exists_subscription(deleted)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
