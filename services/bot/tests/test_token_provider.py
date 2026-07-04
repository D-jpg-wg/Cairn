"""TokenProvider: кэш, ротация refresh, отвязка по 401, single-flight."""

import asyncio
import time
import uuid

import pytest

from app.repositories.bot_repository import BotRepository
from app.services.token_provider import InvalidCodeError, NotLinkedError

TG_ID = 100


async def seed_link(session_factory, user_id: str, refresh: str) -> None:
    async with session_factory() as session:
        await BotRepository(session).upsert(TG_ID, uuid.UUID(user_id), refresh)


async def get_link(session_factory, tg_id: int = TG_ID):
    async with session_factory() as session:
        return await BotRepository(session).get_by_telegram_id(tg_id)


async def test_remember_serves_from_cache(provider, fake_auth):
    provider.remember(TG_ID, "cached-access")
    assert await provider.get_access(TG_ID) == "cached-access"
    assert fake_auth.refresh_calls == 0  # в сеть не ходили


async def test_not_linked_raises(provider):
    with pytest.raises(NotLinkedError):
        await provider.get_access(TG_ID)


async def test_refresh_rotates_token(provider, fake_auth, session_factory):
    fake_auth._mint()  # у auth появляется живой refresh
    await seed_link(session_factory, fake_auth.user_id, fake_auth.live_refresh)

    access = await provider.get_access(TG_ID)

    assert access.startswith("access-")
    link = await get_link(session_factory)
    assert link.refresh_token == fake_auth.live_refresh  # в БД уже новый
    assert fake_auth.refresh_calls == 1


async def test_expired_cache_triggers_refresh(provider, fake_auth, session_factory):
    fake_auth._mint()
    await seed_link(session_factory, fake_auth.user_id, fake_auth.live_refresh)
    provider.remember(TG_ID, "stale-access")
    token, _ = provider._cache[TG_ID]
    provider._cache[TG_ID] = (token, time.monotonic() - 1)  # протух

    access = await provider.get_access(TG_ID)

    assert access != "stale-access"
    assert fake_auth.refresh_calls == 1


async def test_dead_refresh_unlinks(provider, fake_auth, session_factory):
    fake_auth._mint()
    await seed_link(session_factory, fake_auth.user_id, "dead-refresh")

    with pytest.raises(NotLinkedError):
        await provider.get_access(TG_ID)

    assert await get_link(session_factory) is None  # 401 → строка удалена


async def test_single_flight(provider, fake_auth, session_factory):
    """Две конкурентные корутины с пустым кэшем — ровно один refresh.

    Второй refresh со старым токеном получил бы 401 и отвязал юзера —
    double-checked locking в get_access обязан этого не допустить.
    """
    fake_auth._mint()
    await seed_link(session_factory, fake_auth.user_id, fake_auth.live_refresh)

    a, b = await asyncio.gather(provider.get_access(TG_ID), provider.get_access(TG_ID))

    assert a == b
    assert fake_auth.refresh_calls == 1


async def test_link_redeems_code(provider, fake_auth, session_factory):
    code = fake_auth.issue_code()

    await provider.link(TG_ID, code)

    link = await get_link(session_factory)
    assert link is not None
    assert str(link.user_id) == fake_auth.user_id
    assert await provider.get_access(TG_ID)  # access уже в кэше
    assert fake_auth.refresh_calls == 0


async def test_link_code_is_single_use(provider, fake_auth):
    code = fake_auth.issue_code()
    await provider.link(TG_ID, code)

    with pytest.raises(InvalidCodeError):
        await provider.link(TG_ID, code)


async def test_link_invalid_code(provider):
    with pytest.raises(InvalidCodeError):
        await provider.link(TG_ID, "garbage")


async def test_relink_moves_link_to_new_chat(provider, fake_auth, session_factory):
    """Тот же аккаунт из другого чата: старая привязка снесена, кэш выбит."""
    await provider.link(TG_ID, fake_auth.issue_code())
    other_tg = 200

    old = await provider.link(other_tg, fake_auth.issue_code())

    assert old == TG_ID
    assert await get_link(session_factory, TG_ID) is None
    assert (await get_link(session_factory, other_tg)) is not None
    with pytest.raises(NotLinkedError):  # кэш старого чата не пережил перепривязку
        await provider.get_access(TG_ID)


async def test_relink_same_chat_returns_none(provider, fake_auth, session_factory):
    """Повторный /start из того же чата — не «вытеснение», уведомлять некого."""
    await provider.link(TG_ID, fake_auth.issue_code())

    old = await provider.link(TG_ID, fake_auth.issue_code())

    assert old is None
    assert (await get_link(session_factory)) is not None


async def test_repo_replace_link_chat_switches_account(session_factory, fake_auth):
    """Чат был привязан к одному аккаунту, привязывается к другому:
    конфликт по PK telegram_id, его решает upsert-часть replace_link."""
    user_b = uuid.uuid4()
    await seed_link(session_factory, fake_auth.user_id, "r1")

    async with session_factory() as session:
        old = await BotRepository(session).replace_link(TG_ID, user_b, "r2")

    assert old is None  # user_b раньше нигде привязан не был
    link = await get_link(session_factory)
    assert link.user_id == user_b
    assert link.refresh_token == "r2"


async def test_repo_upsert_updates_on_conflict(session_factory, fake_auth):
    """Повторный upsert того же telegram_id обновляет, а не падает."""
    await seed_link(session_factory, fake_auth.user_id, "r1")
    await seed_link(session_factory, fake_auth.user_id, "r2")

    link = await get_link(session_factory)
    assert link.refresh_token == "r2"


async def test_repo_get_by_user_id(session_factory, fake_auth):
    await seed_link(session_factory, fake_auth.user_id, "r1")

    async with session_factory() as session:
        repo = BotRepository(session)
        found = await repo.get_by_user_id(uuid.UUID(fake_auth.user_id))
        missing = await repo.get_by_user_id(uuid.uuid4())

    assert found is not None and found.telegram_id == TG_ID
    assert missing is None
