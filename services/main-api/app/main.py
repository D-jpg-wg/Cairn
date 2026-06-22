from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import entries_router, health_router
from app.core.config import setting
from app.db.db_engine import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=setting.app_name, lifespan=lifespan)

    app.include_router(entries_router, prefix="/api/v1", tags=["entries"])
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    return app


app = create_app()
