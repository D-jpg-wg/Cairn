from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.api import auth_router, health_router
from app.core.config import setting
from app.core.limiter import limiter, rate_limit_handler
from app.db.db_engine import engine

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=setting.app_name, lifespan=lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(health_router, prefix="/api/v1", tags=["health"])

    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
    return app


app = create_app()
