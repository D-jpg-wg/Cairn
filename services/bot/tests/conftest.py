"""Общие фикстуры тестов бота.

Настройки читаются при импорте (`setting = Settings()`), поэтому обязательные
env-переменные выставляем ДО импорта кода приложения. Реальную БД подменяем
тестовым Postgres из testcontainers (upsert требует настоящего постгреса),
auth и main-api — фейками на httpx.MockTransport: сетевых вызовов в тестах нет.
"""

import os
import uuid
from typing import AsyncGenerator, Generator

os.environ.update(
    {
        "DB_NAME": "test",
        "DB_USER": "test",
        "DB_PASSWORD": "test",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "TELEGRAM_BOT_TOKEN": "42:TEST",
        "AUTH_URL": "http://auth.test",
        "MAIN_API_URL": "http://main.test",
        "ACCESS_TTL": "300",
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:1",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer  # noqa: E402

from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402,F401  — регистрирует модели в Base.metadata
from app.services.token_provider import TokenProvider  # noqa: E402


@pytest.fixture(scope="session")
def pg_url() -> Generator[str]:
    """Postgres в контейнере на всю сессию; отдаёт async-URL."""
    with PostgresContainer("postgres:17-alpine") as pg:
        yield pg.get_connection_url().replace("+psycopg2", "+asyncpg")


@pytest_asyncio.fixture
async def engine(pg_url: str) -> AsyncGenerator[AsyncEngine]:
    """Чистая схема на каждый тест."""
    eng = create_async_engine(pg_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(bind=engine, expire_on_commit=False)


class FakeAuth:
    """Стейт-машина auth-сервиса: коды привязки и ротация refresh-токенов.

    Каждый выданный access/refresh уникален (счётчик), «живым» считается
    только последний выданный refresh — как в настоящем auth.
    """

    def __init__(self) -> None:
        self.user_id = str(uuid.uuid4())
        self.codes: set[str] = set()
        self.serial = 0
        self.live_refresh: str | None = None
        self.refresh_calls = 0

    def issue_code(self) -> str:
        code = f"code-{self.serial}"
        self.serial += 1
        self.codes.add(code)
        return code

    def _mint(self) -> dict:
        self.serial += 1
        self.live_refresh = f"refresh-{self.serial}"
        return {
            "access_token": f"access-{self.serial}",
            "refresh_token": self.live_refresh,
            "user_id": self.user_id,
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/link-code/redeem":
            import json

            code = json.loads(request.content)["code"]
            if code not in self.codes:
                return httpx.Response(404, json={"detail": "code not found"})
            self.codes.remove(code)  # код одноразовый
            return httpx.Response(200, json=self._mint())

        if request.url.path == "/api/v1/auth/token/refresh":
            import json

            self.refresh_calls += 1
            token = json.loads(request.content)["refresh_token"]
            if token != self.live_refresh:
                return httpx.Response(401, json={"detail": "invalid refresh"})
            return httpx.Response(200, json=self._mint())

        if request.url.path == "/api/v1/auth/me":
            return httpx.Response(
                200, json={"uuid": self.user_id, "email": "user@test.io"}
            )

        return httpx.Response(404)


class FakeMainApi:
    """Хранилище записей в памяти вместо main-api."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path != "/api/v1/entries/":
            return httpx.Response(404)
        if not request.headers.get("Authorization", "").startswith("Bearer "):
            return httpx.Response(401, json={"detail": "Not authenticated"})

        if request.method == "GET":
            # Повторяем контракт main-api: ?q= фильтрует по title/content
            q = request.url.params.get("q")
            found = [
                e
                for e in self.entries
                if q is None
                or q.lower() in e["title"].lower()
                or q.lower() in (e["content"] or "").lower()
            ]
            return httpx.Response(200, json=found)

        import json

        body = json.loads(request.content)
        needs_url = body.get("type") in ("link", "article", "video")
        if needs_url and not body.get("url"):
            return httpx.Response(422, json={"detail": "url required"})
        entry = {
            "id": str(uuid.uuid4()),
            "title": body["title"],
            "type": body["type"],
            "content": body.get("content"),
            "url": body.get("url"),
            "status": "pending",
            "tags": [],
        }
        self.entries.append(entry)
        return httpx.Response(201, json=entry)


@pytest.fixture
def fake_auth() -> FakeAuth:
    return FakeAuth()


@pytest.fixture
def fake_main() -> FakeMainApi:
    return FakeMainApi()


@pytest_asyncio.fixture
async def auth_http(fake_auth: FakeAuth) -> AsyncGenerator[httpx.AsyncClient]:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(fake_auth.handler), base_url="http://auth.test"
    )
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def main_http(fake_main: FakeMainApi) -> AsyncGenerator[httpx.AsyncClient]:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(fake_main.handler), base_url="http://main.test"
    )
    yield client
    await client.aclose()


@pytest.fixture
def provider(
    auth_http: httpx.AsyncClient, session_factory: async_sessionmaker
) -> TokenProvider:
    return TokenProvider(auth_http, session_factory, access_ttl=300)


# --- стабы Telegram-объектов (совпадают по сигнатурам с aiogram) ---


class FakeUser:
    def __init__(self, tg_id: int) -> None:
        self.id = tg_id


class FakeMessage:
    def __init__(self, tg_id: int, text: str | None = None) -> None:
        self.from_user = FakeUser(tg_id)
        self.text = text
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)

    async def reply(self, text: str, **kwargs) -> None:
        self.answers.append(text)


class FakeCommand:
    def __init__(self, args: str | None) -> None:
        self.args = args


class FakeBotMessage:
    """Сообщение бота с кнопками: то, что редактируют/удаляют колбэки."""

    def __init__(self, source: FakeMessage | None) -> None:
        self.reply_to_message = source
        self.edits: list[str] = []
        self.deleted = False

    async def edit_text(self, text: str, **kwargs) -> None:
        self.edits.append(text)

    async def delete(self) -> None:
        self.deleted = True


class FakeCallback:
    def __init__(self, data: str, tg_id: int, source: FakeMessage | None) -> None:
        self.data = data
        self.from_user = FakeUser(tg_id)
        self.message = FakeBotMessage(source)
        self.alerts: list[str] = []

    async def answer(self, text: str | None = None, **kwargs) -> None:
        if text:
            self.alerts.append(text)
