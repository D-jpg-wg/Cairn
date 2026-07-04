import asyncio
import httpx
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from app import handlers
from app.core.config import setting
from app.db.db_engine import async_session, engine
from app.services.notifier import run_notifier
from app.services.token_provider import TokenProvider


async def main() -> None:
    bot = Bot(token=setting.telegram_bot_token)
    dp = Dispatcher()
    dp.include_routers(handlers.router)
    http = httpx.AsyncClient(base_url=setting.auth_url, timeout=5)
    main_http = httpx.AsyncClient(base_url=setting.main_api_url, timeout=5)
    provider = TokenProvider(http, async_session, setting.access_ttl)
    notifier = asyncio.create_task(run_notifier(bot, async_session))

    await bot.set_my_commands(
        [
            BotCommand(command="entries", description="Мои записи"),
            BotCommand(command="add", description="Сохранить ссылку"),
            BotCommand(command="note", description="Быстрая заметка"),
            BotCommand(command="whoami", description="Кто я"),
            BotCommand(command="find", description="Поиск по записям"),
        ]
    )

    try:
        await dp.start_polling(
            bot, token_provider=provider, auth_http=http, main_http=main_http
        )
    finally:
        notifier.cancel()
        with suppress(asyncio.CancelledError):
            await notifier
        await http.aclose()
        await main_http.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
