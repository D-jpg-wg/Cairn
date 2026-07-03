import asyncio
import os
import httpx

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message

dp = Dispatcher()
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8000")
http = httpx.AsyncClient(base_url=AUTH_URL, timeout=5)

linked: dict[int, dict] = {}


@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    if command.args is None:
        await message.answer("Привет! Пришли /start <код> — код возьми в веб-версии.")
        return
    code = command.args.strip().strip("<>")
    resp = await http.post("/api/v1/auth/link-code/redeem", json={"code": code})
    if resp.status_code != 200:
        await message.answer(
            "Код не подошёл — истёк или уже использован. Возьми новый."
        )
        return
    tokens = resp.json()
    linked[message.from_user.id] = tokens
    await message.answer("Готово, аккаунт привязан!")


@dp.message(Command("whoami"))
async def cmd_whoami(message: Message) -> None:
    tokens = linked.get(message.from_user.id)
    if tokens is None:
        await message.answer("Токен истек, привяжись заного /start <код>. /start <код>")
        return
    resp = await http.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    if resp.status_code != 200:
        await message.answer(
            "Код не подошёл — истёк или уже использован. Возьми новый."
        )
        return
    await message.answer(resp.json()["email"])


@dp.message()
async def fallback(message: Message) -> None:
    pass


async def main() -> None:
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
