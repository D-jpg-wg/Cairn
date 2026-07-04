from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
import httpx

from app import texts
from app.handlers.common import ENTRIES_PATH, bearer
from app.services.token_provider import TokenProvider

router = Router()

KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🔗 Ссылку", callback_data="save:link"),
            InlineKeyboardButton(text="📝 Заметку", callback_data="save:note"),
            InlineKeyboardButton(text="✖️", callback_data="save:cancel"),
        ]
    ]
)


@router.message(F.text, ~F.text.startswith("/"))
async def catch_text(message: Message) -> None:
    """Любой текст без команды — предложение сохранить.
    reply — не косметика: в колбэке исходный текст достаём из reply_to_message.
    """
    await message.reply(texts.WHAT_TO_SAVE, reply_markup=KB)


@router.callback_query(F.data.startswith("save:"))
async def on_save(
    callback: CallbackQuery,
    token_provider: TokenProvider,
    main_http: httpx.AsyncClient,
) -> None:
    action = callback.data.removeprefix("save:")
    if action == "cancel":
        await callback.message.delete()
        await callback.answer()
        return

    source = callback.message.reply_to_message
    if source is None or source.text is None:
        # Telegram отдаёт reply_to_message только для свежих сообщений
        await callback.answer(texts.SOURCE_LOST, show_alert=True)
        return
    text = source.text.strip()

    # from_user колбэка — тот, кто нажал кнопку;
    # message.from_user здесь был бы сам бот
    access = await token_provider.get_access(callback.from_user.id)

    if action == "link":
        payload = {"title": text[:255], "type": "link", "url": text}
    else:
        payload = {"title": text[:255], "type": "note", "content": text}

    resp = await main_http.post(ENTRIES_PATH, json=payload, headers=bearer(access))
    if resp.status_code == 422:
        await callback.answer(texts.NOT_A_LINK, show_alert=True)
        return
    resp.raise_for_status()
    await callback.message.edit_text(texts.SAVED)
    await callback.answer()
