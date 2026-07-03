from sqlalchemy.ext.asyncio import AsyncSession


class BotRepository:
    """."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int):
        pass

    async def upsert(self):
        pass
