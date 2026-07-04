from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
import httpx

from app.services.token_provider import NotLinkedError, TokenProvider

router = Router()

NOT_LINKED = "Аккаунт не привязан. Пришли /start <код> — код возьми в веб-версии."
STATUS_ICON = {"pending": "⏳", "ready": "✅", "failed": "⚠️"}


@router.message(Command("entries"))
async def cmd_entries(
    message: Message,
    token_provider: TokenProvider,
    main_http: httpx.AsyncClient,
) -> None:
    try:
        access = await token_provider.get_access(message.from_user.id)
    except NotLinkedError:
        await message.answer(NOT_LINKED)
        return
    resp = await main_http.get(
        "/api/v1/entries/",
        params={"limit": 10},
        headers={"Authorization": f"Bearer {access}"},
    )
    resp.raise_for_status()
    entries = resp.json()
    if not entries:
        await message.answer("Записей пока нет. Добавь: /add <url> или /note <текст>")
        return

    lines = []
    for entry in entries:
        icon = STATUS_ICON.get(entry["status"], "•")
        title = entry["title"][:60]
        extra = (
            f"\n   {entry['url']}"
            if entry["url"] and entry["url"] != entry["title"]
            else ""
        )
        lines.append(f"{icon} {title}{extra}")
    await message.answer("\n".join(lines), disable_web_page_preview=True)


@router.message(Command("add"))
async def cmd_add(
    message: Message,
    command: CommandObject,
    token_provider: TokenProvider,
    main_http: httpx.AsyncClient,
) -> None:

    if command.args is None:
        await message.answer("Так: /add <url>")
        return
    try:
        access = await token_provider.get_access(message.from_user.id)
    except NotLinkedError:
        await message.answer(NOT_LINKED)
        return

    url = command.args.strip()
    resp = await main_http.post(
        "/api/v1/entries/",
        json={"title": url[:255], "type": "link", "url": url},
        headers={"Authorization": f"Bearer {access}"},
    )
    if resp.status_code == 422:
        await message.answer("Это не похоже на ссылку.")
        return
    resp.raise_for_status()
    await message.answer("Добавил 🔗 — обрабатывается, статус смотри в /entries")


@router.message(Command("note"))
async def cmd_note(
    message: Message,
    command: CommandObject,
    token_provider: TokenProvider,
    main_http: httpx.AsyncClient,
) -> None:
    if command.args is None:
        await message.answer("Так: /note <текст заметки>")
        return
    try:
        access = await token_provider.get_access(message.from_user.id)
    except NotLinkedError:
        await message.answer(NOT_LINKED)
        return

    text = command.args.strip()
    resp = await main_http.post(
        "/api/v1/entries/",
        json={"title": text[:255], "type": "note", "content": text},
        headers={"Authorization": f"Bearer {access}"},
    )
    if resp.status_code == 422:
        await message.answer("Не получилось сохранить заметку.")
        return
    resp.raise_for_status()
    await message.answer("Записал 📝")
