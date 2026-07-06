from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import TelegramObject

from app.services.token_provider import TokenProvider


class AuthMiddleware(BaseMiddleware):
    """Кладёт access-токен в data для хендлеров с flags={"auth": True}.
    Хендлер объявляет параметр access: str и не знает про TokenProvider.
    NotLinkedError не ловим — она улетает в errors.on_not_linked.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not get_flag(data, "auth"):
            return await handler(event, data)

        user = data["event_from_user"]
        provider: TokenProvider = data["token_provider"]
        data["access"] = await provider.get_access(user.id)
        return await handler(event, data)
