from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import setting


engine = create_async_engine(
    setting.db_url, pool_size=10, max_overflow=20, pool_pre_ping=True
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость: выдаёт сессию БД на время запроса и закрывает её после."""
    async with async_session() as session:
        yield session
