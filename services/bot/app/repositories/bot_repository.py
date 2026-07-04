import uuid
from typing import cast

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TelegramLink


class BotRepository:
    """."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> TelegramLink | None:
        return cast(
            TelegramLink | None, await self.session.get(TelegramLink, telegram_id)
        )

    async def upsert(
        self, telegram_id: int, user_id: uuid.UUID, refresh_token: str
    ) -> None:
        stmt = insert(TelegramLink).values(
            telegram_id=telegram_id, user_id=user_id, refresh_token=refresh_token
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[TelegramLink.telegram_id],
            set_={
                "user_id": stmt.excluded.user_id,
                "refresh_token": stmt.excluded.refresh_token,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def delete(self, telegram_id: int) -> None:
        stmt = delete(TelegramLink).where(TelegramLink.telegram_id == telegram_id)
        await self.session.execute(stmt)
        await self.session.commit()
