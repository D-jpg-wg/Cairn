from aiogram import Router

from app.handlers import account, capture, entries, errors, start

router = Router()
# capture ловит любой текст (F.text) — подключаем последним,
# чтобы команды успели совпасть раньше
router.include_routers(
    start.router, account.router, entries.router, capture.router, errors.router
)
