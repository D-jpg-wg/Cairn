import httpx

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.handlers.common import bearer


router = Router()


@router.message(Command("whoami"), flags={"auth": True})
async def whoami(
    message: Message,
    access: str,
    auth_http: httpx.AsyncClient,
) -> None:
    resp = await auth_http.get("/api/v1/auth/me", headers=bearer(access))
    resp.raise_for_status()
    await message.answer(resp.json()["email"])
