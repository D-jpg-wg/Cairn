from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth_router, health_router
from app.core.config import setting
from app.core.limiter import limiter, rate_limit_handler
from app.db.db_engine import engine

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: на остановке закрывает движок БД."""
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Собирает приложение: middleware, роуты и раздача статики."""
    app = FastAPI(title=setting.app_name, lifespan=lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # Нужна для хранения OAuth state между /oauth/google и /callback (защита от CSRF).
    app.add_middleware(SessionMiddleware, secret_key=setting.session_secret)

    # main-app (другой origin) ходит к нам за /refresh и /logout с cookie —
    # для cross-origin запросов с credentials нужен явный origin (не "*").
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[setting.app_url.rstrip("/")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(health_router, prefix="/api/v1", tags=["health"])

    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
    return app


app = create_app()
