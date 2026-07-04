from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
import httpx

from app import texts
from app.handlers.common import ENTRIES_PATH, bearer
from app.services.token_provider import TokenProvider

router = Router()

STATUS_ICON = {"pending": "⏳", "ready": "✅", "failed": "⚠️"}


def _render(entries: list[dict]) -> str:
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
    return "\n".join(lines)


@router.message(Command("entries"))
async def cmd_entries(
    message: Message,
    token_provider: TokenProvider,
    main_http: httpx.AsyncClient,
) -> None:
    access = await token_provider.get_access(message.from_user.id)
    resp = await main_http.get(
        ENTRIES_PATH, params={"limit": 10}, headers=bearer(access)
    )
    resp.raise_for_status()
    entries = resp.json()
    if not entries:
        await message.answer(texts.NO_ENTRIES)
        return
    await message.answer(_render(entries), disable_web_page_preview=True)


@router.message(Command("find"))
async def cmd_find(
    message: Message,
    command: CommandObject,
    token_provider: TokenProvider,
    main_http: httpx.AsyncClient,
) -> None:
    if command.args is None:
        await message.answer(texts.USAGE_FIND)
        return
    access = await token_provider.get_access(message.from_user.id)
    resp = await main_http.get(
        ENTRIES_PATH,
        params={"q": command.args.strip(), "limit": 10},
        headers=bearer(access),
    )
    resp.raise_for_status()
    entries = resp.json()
    if not entries:
        await message.answer(texts.NOT_FOUND)
        return
    await message.answer(_render(entries), disable_web_page_preview=True)


@router.message(Command("add"))
async def cmd_add(
    message: Message,
    command: CommandObject,
    token_provider: TokenProvider,
    main_http: httpx.AsyncClient,
) -> None:
    if command.args is None:
        await message.answer(texts.USAGE_ADD)
        return
    access = await token_provider.get_access(message.from_user.id)
    url = command.args.strip()
    resp = await main_http.post(
        ENTRIES_PATH,
        json={"title": url[:255], "type": "link", "url": url},
        headers=bearer(access),
    )
    if resp.status_code == 422:
        await message.answer(texts.NOT_A_LINK)
        return
    resp.raise_for_status()
    await message.answer(texts.ADDED_LINK)


@router.message(Command("note"))
async def cmd_note(
    message: Message,
    command: CommandObject,
    token_provider: TokenProvider,
    main_http: httpx.AsyncClient,
) -> None:
    if command.args is None:
        await message.answer(texts.USAGE_NOTE)
        return
    access = await token_provider.get_access(message.from_user.id)
    text = command.args.strip()
    resp = await main_http.post(
        ENTRIES_PATH,
        json={"title": text[:255], "type": "note", "content": text},
        headers=bearer(access),
    )
    if resp.status_code == 422:
        await message.answer(texts.NOTE_FAILED)
        return
    resp.raise_for_status()
    await message.answer(texts.ADDED_NOTE)
