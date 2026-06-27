from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import entries_router, health_router, me_router
from app.core.config import setting
from app.db.db_engine import engine

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: на остановке закрывает движок БД."""
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Собирает приложение: роуты и раздача статики."""
    app = FastAPI(title=setting.app_name, lifespan=lifespan)

    app.include_router(entries_router, prefix="/api/v1/entries", tags=["entries"])
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(me_router, prefix="/api/v1", tags=["me"])

    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
    return app


app = create_app()
