from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class AuthRepository:
    """Класс работы с бд."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = await self.session.execute(select(User).where(User.email == email))
        return stmt.scalars().first()

    async def get_by_uuid(self, uuid: str) -> User | None:
        stmt = await self.session.execute(select(User).where(User.uuid == uuid))
        return stmt.scalars().first()

    async def create(self, email: str, hashed_password: str) -> User:
        user = User(email=email, hashed_password=hashed_password)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
