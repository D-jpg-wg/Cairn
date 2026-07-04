import asyncio
import httpx

from aiogram import Bot, Dispatcher

from app import handlers
from app.core.config import setting
from app.db.db_engine import async_session, engine
from app.services.token_provider import TokenProvider


async def main() -> None:
    bot = Bot(token=setting.telegram_bot_token)
    dp = Dispatcher()
    dp.include_routers(handlers.router)
    http = httpx.AsyncClient(base_url=setting.auth_url, timeout=5)
    provider = TokenProvider(http, async_session, setting.access_ttl)

    try:
        await dp.start_polling(bot, token_provider=provider, auth_http=http)
    finally:
        await http.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
