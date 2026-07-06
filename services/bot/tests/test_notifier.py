"""Дайджест статей: батчинг в окне, мгновенная отправка личных записей."""

import asyncio
import uuid

from app.repositories.bot_repository import BotRepository
from app.services.notifier import ArticleDigest, _handle_entry_created
from tests.conftest import FakeBot

TG_ID = 100
WINDOW = 0.05  # маленькое окно — тесты не ждут реальную минуту


async def seed_link(session_factory, user_id: str, tg_id: int = TG_ID) -> None:
    async with session_factory() as session:
        await BotRepository(session).upsert(tg_id, uuid.UUID(user_id), "refresh")


def article_event(user_id: str, title: str, url: str | None = None) -> dict:
    return {"owner_id": user_id, "type": "article", "title": title, "url": url}


def note_event(user_id: str) -> dict:
    return {"owner_id": user_id, "type": "note", "title": "Заметка", "url": None}


async def test_articles_are_batched_into_one_message(session_factory):
    user_id = str(uuid.uuid4())
    await seed_link(session_factory, user_id)
    bot = FakeBot()
    digest = ArticleDigest(bot, window_seconds=WINDOW)

    for title in ["Первая", "Вторая", "Третья"]:
        await _handle_entry_created(
            article_event(user_id, title), session_factory, bot, digest
        )

    assert bot.sent == []  # окно ещё не истекло — сообщения нет
    await asyncio.sleep(WINDOW * 2)

    assert len(bot.sent) == 1
    chat_id, text = bot.sent[0]
    assert chat_id == TG_ID
    assert "3" in text
    assert "Первая" in text and "Вторая" in text and "Третья" in text


async def test_personal_entry_sent_instantly(session_factory):
    user_id = str(uuid.uuid4())
    await seed_link(session_factory, user_id)
    bot = FakeBot()
    digest = ArticleDigest(bot, window_seconds=WINDOW)

    await _handle_entry_created(note_event(user_id), session_factory, bot, digest)

    assert len(bot.sent) == 1  # без ожидания окна


async def test_unlinked_user_gets_nothing(session_factory):
    user_id = str(uuid.uuid4())  # никогда не привязывал telegram
    bot = FakeBot()
    digest = ArticleDigest(bot, window_seconds=WINDOW)

    await _handle_entry_created(
        article_event(user_id, "Статья"), session_factory, bot, digest
    )
    await asyncio.sleep(WINDOW * 2)

    assert bot.sent == []


async def test_aclose_flushes_pending_immediately():
    """На остановке бота дайджест не должен ждать полное окно (60с в проде)."""
    bot = FakeBot()
    digest = ArticleDigest(bot, window_seconds=60.0)
    digest.add(TG_ID, "Статья", None)

    await digest.aclose()

    assert len(bot.sent) == 1


async def test_two_chats_do_not_mix_digests(session_factory):
    user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())
    await seed_link(session_factory, user_a, tg_id=100)
    await seed_link(session_factory, user_b, tg_id=200)
    bot = FakeBot()
    digest = ArticleDigest(bot, window_seconds=WINDOW)

    await _handle_entry_created(
        article_event(user_a, "A"), session_factory, bot, digest
    )
    await _handle_entry_created(
        article_event(user_b, "B"), session_factory, bot, digest
    )
    await asyncio.sleep(WINDOW * 2)

    assert len(bot.sent) == 2
    by_chat = {chat_id: text for chat_id, text in bot.sent}
    assert "A" in by_chat[100] and "B" not in by_chat[100]
    assert "B" in by_chat[200] and "A" not in by_chat[200]
