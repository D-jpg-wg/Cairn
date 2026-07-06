"""AuthMiddleware: выдача access-токена хендлерам с flags={"auth": True}.

Middleware зовём напрямую, без Dispatcher. get_flag читает флаги из
data["handler"] (HandlerObject сматчившегося хендлера) — собираем его руками,
как это делает aiogram при диспетчеризации.
"""

import pytest
from aiogram.dispatcher.event.handler import HandlerObject

from app.middlewares.auth import AuthMiddleware
from app.services.token_provider import NotLinkedError
from tests.conftest import FakeUser

TG_ID = 100


async def _handler(event, data):
    """Следующее звено цепочки: возвращает то, что видит хендлер."""
    return data.get("access")


def data_for(provider, flags: dict) -> dict:
    return {
        "handler": HandlerObject(callback=_handler, flags=flags),
        "event_from_user": FakeUser(TG_ID),
        "token_provider": provider,
    }


async def test_no_flag_passes_through(provider):
    """Без флага auth middleware прозрачна: за токеном не ходит.

    provider здесь без привязки — попытка get_access подняла бы NotLinkedError.
    """
    data = data_for(provider, flags={})
    result = await AuthMiddleware()(_handler, None, data)
    assert result is None
    assert "access" not in data


async def test_flag_injects_access(provider, fake_auth):
    await provider.link(TG_ID, fake_auth.issue_code())
    data = data_for(provider, flags={"auth": True})

    result = await AuthMiddleware()(_handler, None, data)

    assert result == data["access"]  # хендлер получил тот же токен
    assert data["access"].startswith("access-")


async def test_flag_unlinked_raises(provider):
    """Привязки нет — NotLinkedError летит наружу, в errors.on_not_linked."""
    data = data_for(provider, flags={"auth": True})
    with pytest.raises(NotLinkedError):
        await AuthMiddleware()(_handler, None, data)
