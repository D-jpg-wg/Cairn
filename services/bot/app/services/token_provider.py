import time
import uuid
from asyncio import Lock

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.bot_repository import BotRepository


class NotLinkedError(Exception):
    """Привязки нет или она умерла — хендлер должен попросить /start <код>."""

    pass


class TokenProvider:
    """Выдаёт валидный access-токен для telegram_id.
    Кэш access в памяти, refresh в БД; ротация refresh и отвязка по 401 — внутри,
    хендлеры про refresh-токены не знают.
    """

    def __init__(
        self,
        http: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        access_ttl: int,
    ) -> None:
        self.http = http
        self.session_factory = session_factory
        self.access_ttl = access_ttl
        self._cache: dict[int, tuple[str, float]] = {}
        self._locks: dict[int, Lock] = {}

    def remember(self, telegram_id: int, access_token: str) -> None:
        """Кладёт свежий access в кэш — /start зовёт это после redeem."""
        self._cache[telegram_id] = (access_token, time.monotonic() + self.access_ttl)

    def _cached(self, telegram_id: int) -> str | None:
        entry = self._cache.get(telegram_id)
        if entry is None:
            return None
        access, deadline = entry
        if time.monotonic() >= deadline:
            return None
        return access

    async def get_access(self, telegram_id: int) -> str:
        """Access из кэша или через рефреш; NotLinkedError, если привязки нет."""
        access = self._cached(telegram_id)
        if access is not None:
            return access

        lock = self._locks.setdefault(telegram_id, Lock())

        async with lock:
            access = self._cached(telegram_id)
            if access is not None:
                return access
            return await self._refresh(telegram_id)

    async def _refresh(self, telegram_id: int) -> str:
        async with self.session_factory() as session:
            repo = BotRepository(session)
            link = await repo.get_by_telegram_id(telegram_id)
            if link is None:
                raise NotLinkedError

            resp = await self.http.post(
                "/api/v1/auth/token/refresh", json={"refresh_token": link.refresh_token}
            )
            if resp.status_code == 401:
                await repo.delete(telegram_id)
                self._cache.pop(telegram_id, None)
                raise NotLinkedError
            resp.raise_for_status()

            body = resp.json()
            await repo.upsert(
                telegram_id, uuid.UUID(body["user_id"]), body["refresh_token"]
            )
        self.remember(telegram_id, body["access_token"])
        return body["access_token"]
