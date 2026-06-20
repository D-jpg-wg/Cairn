from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.core.config import setting
from app.db.db_engine import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=setting.app_name, lifespan=lifespan)
    app.include_router(auth_router)

    return app


app = create_app()
