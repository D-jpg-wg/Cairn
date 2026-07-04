import httpx

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.token_provider import NotLinkedError, TokenProvider


router = Router()


@router.message(Command("whoami"))
async def whoami(
    message: Message,
    token_provider: TokenProvider,
    auth_http: httpx.AsyncClient,
) -> None:
    try:
        access = await token_provider.get_access(message.from_user.id)
    except NotLinkedError:
        await message.answer(
            "Аккаунт не привязан. Пришли /start <код> — код возьми в веб-версии."
        )
        return
    resp = await auth_http.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    resp.raise_for_status()
    await message.answer(resp.json()["email"])
