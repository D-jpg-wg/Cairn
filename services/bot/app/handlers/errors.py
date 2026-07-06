from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent

from app import texts
from app.services.token_provider import NotLinkedError

router = Router()


@router.errors(ExceptionTypeFilter(NotLinkedError))
async def on_not_linked(event: ErrorEvent) -> None:
    """NotLinkedError из любого хендлера оседает здесь — одно место вместо шести.

    AuthMiddleware зовёт get_access без try/except; как exception handlers в FastAPI.
    """
    if event.update.message:
        await event.update.message.answer(texts.NOT_LINKED)
    elif event.update.callback_query:
        # Сообщением не ответить — только алерт поверх кнопок.
        await event.update.callback_query.answer(texts.NOT_LINKED, show_alert=True)
