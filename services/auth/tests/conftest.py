"""Общие фикстуры тестов auth-сервиса.

Важно: настройки сервиса читаются при импорте (`setting = Setting()`), поэтому
обязательные env-переменные выставляем ДО импорта кода приложения. Реальную БД
подменяем тестовым Postgres из testcontainers, внешние вызовы (Google) — моками.
"""

import os
from typing import Generator, AsyncGenerator

os.environ.update(
    {
        "APP_NAME": "cairn-auth-test",
        "DB_NAME": "test",
        "DB_USER": "test",
        "DB_PASSWORD": "test",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "GOOGLE_CLIENT_ID": "test-client-id",
        "GOOGLE_CLIENT_SECRET": "test-client-secret",
        "GOOGLE_REDIRECT_URL": "http://testserver/api/v1/auth/oauth/google/callback",
        "SESSION_SECRET": "test-session-secret",
        "ENVIRONMENT": "dev",
    }
)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402

from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402,F401  — регистрирует модели в Base.metadata


@pytest.fixture(scope="session")
def pg_url() -> Generator[str]:
    """Поднимает Postgres в контейнере на всю сессию и отдаёт async-URL."""
    with PostgresContainer("postgres:17-alpine") as pg:
        # testcontainers ждёт готовности через psycopg2; для приложения нужен asyncpg.
        yield pg.get_connection_url().replace("+psycopg2", "+asyncpg")


@pytest_asyncio.fixture
async def engine(pg_url):
    """Чистая схема на каждый тест: создаём таблицы и обнуляем данные."""
    eng = create_async_engine(pg_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("TRUNCATE users, refresh_tokens RESTART IDENTITY CASCADE")
        )
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient]:
    """HTTP-клиент к приложению с подменённой сессией БД и выключенным rate-limit."""
    from app.core.limiter import limiter
    from app.db.db_engine import get_async_session
    from app.main import app

    limiter.enabled = False
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()
