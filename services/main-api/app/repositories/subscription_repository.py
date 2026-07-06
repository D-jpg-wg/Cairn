from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription


class SubscriptionRepository:
    """Доступ к подпискам юзеров на ленты."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: UUID, feed_url: str) -> Subscription:
        """Создаёт подписку; повторная на ту же ленту — no-op (unique user_id+feed_url)."""
        stmt = (
            pg_insert(Subscription)
            .values(user_id=user_id, feed_url=feed_url)
            .on_conflict_do_nothing(index_elements=["user_id", "feed_url"])
            .returning(Subscription.id)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        sub_id = result.scalar()
        if sub_id is None:
            existing = await self.session.execute(
                select(Subscription).where(
                    Subscription.user_id == user_id,
                    Subscription.feed_url == feed_url,
                )
            )
            return existing.scalars().one()
        created = await self.session.get(Subscription, sub_id)
        assert created is not None
        return created

    async def get_all(self, user_id: UUID) -> list[Subscription]:
        """Подписки юзера, новые сверху."""
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(
        self, subscription_id: UUID, user_id: UUID
    ) -> Optional[Subscription]:
        """Удаляет подписку юзера и возвращает её (или None, если не найдена)."""
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.id == subscription_id, Subscription.user_id == user_id
            )
        )
        subscription = result.scalars().first()
        if subscription is None:
            return None
        await self.session.delete(subscription)
        await self.session.commit()
        return subscription

    async def get_all_feed_urls(self) -> list[str]:
        """Все ленты, на которые хоть кто-то подписан — список для парсера."""
        result = await self.session.execute(select(Subscription.feed_url).distinct())
        return list(result.scalars().all())
