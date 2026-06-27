from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.refresh_token import RefreshToken


class AuthRepository:
    """Класс работы с бд."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_refresh_token(
        self, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> None:
        """Сохраняет хэш refresh-токена с привязкой к пользователю и сроком жизни."""
        self.session.add(
            RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        )
        await self.session.commit()

    async def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        """Находит запись refresh-токена по его хэшу (или None)."""
        res = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return res.scalars().first()

    async def revoke_refresh_token(self, token: RefreshToken) -> None:
        """Помечает refresh-токен отозванным."""
        token.revoked = True
        await self.session.commit()

    async def get_by_email(self, email: str) -> User | None:
        """Находит пользователя по email (или None)."""
        stmt = await self.session.execute(select(User).where(User.email == email))
        return stmt.scalars().first()

    async def get_by_uuid(self, uuid: str) -> User | None:
        """Находит пользователя по uuid (или None)."""
        stmt = await self.session.execute(select(User).where(User.uuid == uuid))
        return stmt.scalars().first()

    async def create(self, email: str, hashed_password: str | None = None) -> User:
        """Создаёт пользователя; пароль необязателен (у OAuth-юзеров его нет)."""
        user = User(email=email, hashed_password=hashed_password)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
