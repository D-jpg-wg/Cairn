from datetime import datetime, timezone
from fastapi import HTTPException
from starlette import status

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    generate_link_code,
)
from app.core.tokens import REFRESH_TTL, LINK_CODE_TTL
from app.models import User
from app.repositories.user_repository import AuthRepository
from app.schemas.user import UserCreate, LoginRequest


class AuthService:
    """Бизнес-логика аутентификации: регистрация, вход и жизненный цикл токенов."""

    def __init__(self, repo: AuthRepository) -> None:
        self.repo = repo

    async def register(self, body: UserCreate) -> User:
        """Создаёт пользователя; 409, если email уже занят."""
        if await self.repo.get_by_email(body.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
            )

        return await self.repo.create(
            email=body.email, hashed_password=hash_password(body.password)
        )

    async def issue_tokens(self, user: User) -> tuple[str, str]:
        """Пара токенов: короткий access (JWT) + длинный refresh (случайная строка).
        В БД кладём ХЭШ refresh, наружу отдаём сырой токен."""
        access = create_access_token(str(user.uuid))
        raw_refresh = generate_refresh_token()
        await self.repo.create_refresh_token(
            user_id=user.uuid,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=datetime.now(timezone.utc) + REFRESH_TTL,
        )
        return access, raw_refresh

    async def login(self, body: LoginRequest) -> tuple[str, str]:
        """Проверяет email/пароль и выдаёт пару токенов; 401 при неверных данных."""
        user = await self.repo.get_by_email(body.email)
        if not user or not verify_password(body.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        return await self.issue_tokens(user)

    async def login_oauth(self, email: str) -> tuple[str, str]:
        """Логин по подтверждённому провайдером email: найти или создать юзера."""
        user = await self.repo.get_by_email(email)
        if not user:
            user = await self.repo.create(email=email)
        return await self.issue_tokens(user)

    async def refresh(self, raw_refresh: str) -> tuple[str, str]:
        """Меняет валидный refresh на новую пару. Старый гасим — это ротация."""
        token = await self.repo.get_refresh_token(hash_refresh_token(raw_refresh))
        if not token or token.revoked or token.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect refresh token",
            )
        await self.repo.revoke_refresh_token(token)
        user = await self.repo.get_by_uuid(str(token.user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return await self.issue_tokens(user)

    async def logout(self, raw_refresh: str) -> None:
        token = await self.repo.get_refresh_token(hash_refresh_token(raw_refresh))
        if token:
            await self.repo.revoke_refresh_token(token)

    async def create_link_code(self, user: User) -> str:
        """Выдает одноразовый код привязки: в БД кладем хэш, наружу - сырой код."""
        raw = generate_link_code()
        await self.repo.create_link_code(
            user_id=user.uuid,
            code_hash=hash_refresh_token(raw),
            expires_at=datetime.now(timezone.utc) + LINK_CODE_TTL,
        )
        return raw

    async def redeem_link_code(self, raw_code: str) -> tuple[str, str]:
        """меняет валидный код на пару токенов и гасит код (одноразовость)."""
        link = await self.repo.get_link_code(hash_refresh_token(raw_code))
        if not link or link.used or link.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired link",
            )
        await self.repo.mark_link_code_used(link)
        user = await self.repo.get_by_uuid(str(link.user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return await self.issue_tokens(user)
