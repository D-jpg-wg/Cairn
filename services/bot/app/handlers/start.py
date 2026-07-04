from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from app import texts
from app.services.token_provider import InvalidCodeError, TokenProvider


router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    token_provider: TokenProvider,
) -> None:
    if command.args is None:
        await message.answer(texts.START_HINT)
        return

    code = command.args.strip().strip("<>")
    try:
        await token_provider.link(message.from_user.id, code)
    except InvalidCodeError:
        await message.answer(texts.CODE_REJECTED)
        return

    await message.answer(texts.LINKED_OK)
