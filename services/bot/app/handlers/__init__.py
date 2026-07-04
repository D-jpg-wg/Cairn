from aiogram import Router

from app.handlers import account, entries, start

router = Router()
router.include_routers(start.router)
router.include_routers(account.router)
router.include_routers(entries.router)
