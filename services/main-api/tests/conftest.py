"""Общие фикстуры тестов main-api.

main-api только ПРОВЕРЯЕТ JWT (публичным ключом auth). Чтобы тесты были
самодостаточными и не лезли в файлы auth-сервиса, генерируем СВОЮ тестовую пару
ключей: публичный отдаём приложению (через JWT_PUBLIC_KEY_PATH), приватным
подписываем токены в тестах — ровно так, как это делал бы auth.

Всё это до импорта приложения: настройки и ключ читаются на импорте.
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_PEM = _key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
PUBLIC_PEM = (
    _key.public_key()
    .public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)

_fd, _pub_path = tempfile.mkstemp(suffix="_jwt_public.pem")
with os.fdopen(_fd, "w") as _f:
    _f.write(PUBLIC_PEM)

os.environ.update(
    {
        "APP_NAME": "cairn-main-api-test",
        "DB_NAME": "test",
        "DB_USER": "test",
        "DB_PASSWORD": "test",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "JWT_PUBLIC_KEY_PATH": _pub_path,
    }
)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402

from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402,F401  — регистрирует модели в Base.metadata

_ALGORITHM = "RS256"


def make_token(
    user_id, *, key: str = PRIVATE_PEM, exp: timedelta = timedelta(minutes=15)
) -> str:
    """Подписывает JWT как это делал бы auth (sub = uuid пользователя)."""
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + exp},
        key,
        algorithm=_ALGORITHM,
    )


@pytest.fixture
def make_jwt():
    """Фабрика токенов (можно передать свой key/exp для негативных кейсов)."""
    return make_token


@pytest.fixture
def user_a() -> str:
    return str(uuid4())


@pytest.fixture
def user_b() -> str:
    return str(uuid4())


@pytest.fixture
def auth():
    """auth(user_id) -> заголовки с Bearer-токеном этого пользователя."""

    def _auth(user_id) -> dict:
        return {"Authorization": f"Bearer {make_token(user_id)}"}

    return _auth


@pytest.fixture(scope="session")
def pg_url() -> str:
    with PostgresContainer("postgres:17-alpine") as pg:
        yield pg.get_connection_url().replace("+psycopg2", "+asyncpg")


@pytest_asyncio.fixture
async def engine(pg_url):
    """Чистая схема на каждый тест."""
    eng = create_async_engine(pg_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("TRUNCATE entries, tags, entry_tags RESTART IDENTITY CASCADE")
        )
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def client(engine) -> AsyncClient:
    from app.db.db_engine import get_async_session
    from app.main import app

    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def task_db(pg_url, monkeypatch):
    """Подменяет SyncSession задачи на сессию к тестовому Postgres + чистая схема.

    Задача внутри делает `with SyncSession()`, а та смотрит в боевую БД, поэтому
    подменяем имя SyncSession в модуле задачи на sessionmaker к контейнеру.
    """
    sync_engine = create_engine(pg_url.replace("+asyncpg", "+psycopg2"))
    Base.metadata.create_all(sync_engine)
    sync_maker = sessionmaker(bind=sync_engine, expire_on_commit=False)
    with sync_maker() as session:
        session.execute(
            text("TRUNCATE entries, tags, entry_tags RESTART IDENTITY CASCADE")
        )
        session.commit()
    monkeypatch.setattr("app.worker.tasks.SyncSession", sync_maker)
    yield sync_maker
    sync_engine.dispose()
