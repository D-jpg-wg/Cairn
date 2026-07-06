"""Хендлеры: /start, /whoami, entries-команды и capture-кнопки.

Хендлеры зовём напрямую со стабами вместо aiogram-объектов — фильтры и DI
здесь не проверяются (это территория интеграционного прогона), только логика.
Access-токен хендлерам выдаёт AuthMiddleware, поэтому тесты передают готовую
строку ACCESS; случай «привязки нет» проверяется в test_auth_middleware.py,
а ответ юзеру на NotLinkedError — тестами errors-хендлера ниже.
"""

from app import texts
from app.handlers.account import whoami
from app.handlers.capture import catch_text, on_cancel, on_save
from app.handlers.entries import cmd_add, cmd_entries, cmd_find, cmd_note
from app.handlers.errors import on_not_linked
from app.handlers.start import cmd_start
from tests.conftest import FakeCallback, FakeCommand, FakeMessage

TG_ID = 100
ACCESS = "access-token"


# --- /start ---


async def test_start_without_code(provider):
    msg = FakeMessage(TG_ID)
    await cmd_start(msg, FakeCommand(None), provider)
    assert any("код возьми" in a for a in msg.answers)


async def test_start_bad_code(provider):
    msg = FakeMessage(TG_ID)
    await cmd_start(msg, FakeCommand("<wrong>"), provider)
    assert any("не подошёл" in a for a in msg.answers)


async def test_start_links_account(provider, fake_auth):
    msg = FakeMessage(TG_ID)
    await cmd_start(msg, FakeCommand(f"<{fake_auth.issue_code()}>"), provider)
    assert any("привязан" in a for a in msg.answers)
    assert msg.bot.sent == []  # вытеснять было некого


async def test_start_relink_notifies_old_chat(provider, fake_auth):
    await provider.link(TG_ID, fake_auth.issue_code())
    msg = FakeMessage(200)

    await cmd_start(msg, FakeCommand(fake_auth.issue_code()), provider)

    assert any("привязан" in a for a in msg.answers)
    assert msg.bot.sent == [(TG_ID, texts.LINK_MOVED)]


async def test_start_relink_survives_blocked_old_chat(provider, fake_auth):
    """Старый чат заблокировал бота — привязка всё равно успешна."""
    await provider.link(TG_ID, fake_auth.issue_code())
    msg = FakeMessage(200)
    msg.bot.fail = True

    await cmd_start(msg, FakeCommand(fake_auth.issue_code()), provider)

    assert any("привязан" in a for a in msg.answers)


# --- /whoami ---


async def test_whoami(auth_http):
    msg = FakeMessage(TG_ID)
    await whoami(msg, ACCESS, auth_http)
    assert msg.answers == ["user@test.io"]


# --- entries-команды ---


async def test_entries_empty(main_http):
    msg = FakeMessage(TG_ID)
    await cmd_entries(msg, ACCESS, main_http)
    assert any("пока нет" in a for a in msg.answers)


async def test_add_and_list(main_http, fake_main):
    msg = FakeMessage(TG_ID)
    await cmd_add(msg, FakeCommand("https://example.com/x"), ACCESS, main_http)
    assert any("Добавил" in a for a in msg.answers)
    assert fake_main.entries[0]["url"] == "https://example.com/x"

    msg = FakeMessage(TG_ID)
    await cmd_entries(msg, ACCESS, main_http)
    assert "example.com/x" in "\n".join(msg.answers)


async def test_note(main_http, fake_main):
    msg = FakeMessage(TG_ID)
    await cmd_note(msg, FakeCommand("мысль"), ACCESS, main_http)
    assert any("Записал" in a for a in msg.answers)
    assert fake_main.entries[0]["content"] == "мысль"


async def test_add_usage_hint(main_http):
    msg = FakeMessage(TG_ID)
    await cmd_add(msg, FakeCommand(None), ACCESS, main_http)
    assert any("Так:" in a for a in msg.answers)


# --- /find ---


async def test_find_usage_hint(main_http):
    msg = FakeMessage(TG_ID)
    await cmd_find(msg, FakeCommand(None), ACCESS, main_http)
    assert any("Так:" in a for a in msg.answers)


async def test_find_filters_entries(main_http):
    await cmd_note(
        FakeMessage(TG_ID), FakeCommand("заметка про kafka"), ACCESS, main_http
    )
    await cmd_note(
        FakeMessage(TG_ID), FakeCommand("заметка про grpc"), ACCESS, main_http
    )

    msg = FakeMessage(TG_ID)
    await cmd_find(msg, FakeCommand("kafka"), ACCESS, main_http)

    text = "\n".join(msg.answers)
    assert "про kafka" in text
    assert "grpc" not in text  # главный assert: поиск, а не «показать всё»


async def test_find_no_matches(main_http):
    await cmd_note(
        FakeMessage(TG_ID), FakeCommand("заметка про kafka"), ACCESS, main_http
    )

    msg = FakeMessage(TG_ID)
    await cmd_find(msg, FakeCommand("такого-нет"), ACCESS, main_http)
    assert any("не нашлось" in a for a in msg.answers)


async def test_render_dedups_title_equal_url(main_http):
    """title == url (как делает /add) — ссылка в выводе не дублируется."""
    url = "https://example.com/dedup"
    await cmd_add(FakeMessage(TG_ID), FakeCommand(url), ACCESS, main_http)

    msg = FakeMessage(TG_ID)
    await cmd_entries(msg, ACCESS, main_http)
    assert "\n".join(msg.answers).count(url) == 1


# --- capture: текст + inline-кнопки ---


async def test_catch_text_offers_buttons():
    msg = FakeMessage(TG_ID, "просто текст")
    await catch_text(msg)
    assert any("Что сохранить" in a for a in msg.answers)


async def test_save_note_callback(main_http, fake_main):
    cb = FakeCallback("save:note", TG_ID, FakeMessage(TG_ID, "текст заметки"))
    await on_save(cb, ACCESS, main_http)
    assert "Сохранил ✅" in cb.message.edits
    assert fake_main.entries[0]["content"] == "текст заметки"


async def test_save_link_callback(main_http, fake_main):
    cb = FakeCallback("save:link", TG_ID, FakeMessage(TG_ID, "https://e.com"))
    await on_save(cb, ACCESS, main_http)
    assert fake_main.entries[0]["url"] == "https://e.com"


async def test_save_cancel_deletes_prompt():
    cb = FakeCallback("save:cancel", TG_ID, FakeMessage(TG_ID, "x"))
    await on_cancel(cb)
    assert cb.message.deleted


async def test_save_lost_source_alerts(main_http):
    """Telegram не отдал reply_to_message (старое сообщение) — алерт, не падение."""
    cb = FakeCallback("save:note", TG_ID, None)
    await on_save(cb, ACCESS, main_http)
    assert any("потерялось" in a for a in cb.alerts)


# --- errors-хендлер: единая точка ответа на NotLinkedError ---


class FakeUpdate:
    def __init__(self, message=None, callback_query=None) -> None:
        self.message = message
        self.callback_query = callback_query


class FakeErrorEvent:
    def __init__(self, update: FakeUpdate) -> None:
        self.update = update


async def test_error_handler_answers_message():
    msg = FakeMessage(TG_ID)
    await on_not_linked(FakeErrorEvent(FakeUpdate(message=msg)))
    assert any("не привязан" in a for a in msg.answers)


async def test_error_handler_alerts_callback():
    cb = FakeCallback("save:note", TG_ID, None)
    await on_not_linked(FakeErrorEvent(FakeUpdate(callback_query=cb)))
    assert any("не привязан" in a for a in cb.alerts)
