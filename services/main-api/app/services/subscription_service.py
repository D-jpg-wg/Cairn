from typing import Optional
from uuid import UUID

from app.models import Subscription
from app.repositories.subscription_repository import SubscriptionRepository


class SubscriptionService:
    """Подписки юзеров на ленты; парсер про юзеров не знает — только про фиды."""

    def __init__(self, repo: SubscriptionRepository) -> None:
        self.repo = repo

    async def create(self, user_id: UUID, feed_url: str) -> Subscription:
        return await self.repo.create(user_id, feed_url)

    async def get_all(self, user_id: UUID) -> list[Subscription]:
        return await self.repo.get_all(user_id)

    async def delete(
        self, subscription_id: UUID, user_id: UUID
    ) -> Optional[Subscription]:
        return await self.repo.delete(subscription_id, user_id)

    async def get_all_feed_urls(self) -> list[str]:
        return await self.repo.get_all_feed_urls()
