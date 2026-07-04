from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from app.services.token_provider import InvalidCodeError, TokenProvider


router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    token_provider: TokenProvider,
) -> None:
    if command.args is None:
        await message.answer("Привет! Пришли /start <код> — код возьми в веб-версии.")
        return

    code = command.args.strip().strip("<>")
    try:
        await token_provider.link(message.from_user.id, code)
    except InvalidCodeError:
        await message.answer(
            "Код не подошёл — истёк или уже использован. Возьми новый."
        )
        return

    await message.answer("Готово, аккаунт привязан!")
