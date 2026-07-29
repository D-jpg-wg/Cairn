import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    entries_router,
    feeds_router,
    health_router,
    me_router,
    subscriptions_router,
)
from app.core.config import setting
from app.db.db_engine import engine
from app.grpc_client import start_search_client, stop_search_client
from app.kafka.messaging import start_producer, stop_producer
from app.kafka.consumer import run_page_consumer

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: на остановке закрывает движок БД."""
    await start_producer()
    await start_search_client()
    consumer_task = asyncio.create_task(run_page_consumer())
    yield
    consumer_task.cancel()
    with suppress(asyncio.CancelledError):
        await consumer_task
    await stop_search_client()
    await stop_producer()
    await engine.dispose()


def create_app() -> FastAPI:
    """Собирает приложение: роуты и раздача статики."""
    app = FastAPI(
        title=setting.app_name,
        lifespan=lifespan,
        default_response_class=ORJSONResponse,
    )

    app.include_router(entries_router, prefix="/api/v1/entries", tags=["entries"])
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(me_router, prefix="/api/v1", tags=["me"])
    app.include_router(
        subscriptions_router, prefix="/api/v1/subscriptions", tags=["subscriptions"]
    )
    app.include_router(feeds_router, prefix="/api/v1", tags=["feeds"])
    Instrumentator().instrument(app).expose(app)

    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
    return app


app = create_app()
