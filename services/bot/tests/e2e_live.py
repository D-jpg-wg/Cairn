"""Живой e2e: вся цепочка против настоящих auth, main-api, bot-db и Kafka.

В отличие от tests/test_* (офлайн, свой Postgres) требует поднятый compose-стек:
    docker compose up -d auth main-api bot-db kafka
Перед запуском останови бота в compose: docker compose stop bot.
Иначе два конфликта: его консьюмер в той же группе bot-notifier перехватит
событие теста 16, а привязка тестового юзера будет мигать в общей bot-db.
Запуск из services/bot:
    PYTHONPATH=. .venv/bin/python tests/e2e_live.py
Имя без test_-префикса намеренно: pytest его не собирает.
"""

import asyncio
import time
import uuid

import httpx
from aiogram.dispatcher.event.handler import HandlerObject

from app.core.config import setting
from app.db.db_engine import async_session, engine
from app.handlers.account import whoami
from app.handlers.capture import catch_text, on_cancel, on_save
from app.middlewares.auth import AuthMiddleware
from app.services.notifier import run_notifier
from app.handlers.entries import cmd_add, cmd_entries, cmd_note
from app.handlers.start import cmd_start
from app.repositories.bot_repository import BotRepository
from app.services.token_provider import (
    InvalidCodeError,
    NotLinkedError,
    TokenProvider,
)

TG_ID = 990_001  # тестовый telegram_id, чистим до и после

passed = 0
failed = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} {extra}")


class FakeUser:
    def __init__(self, tg_id: int) -> None:
        self.id = tg_id


class FakeMessage:
    """Минимальный стаб aiogram Message: from_user.id + answer()."""

    def __init__(self, tg_id: int) -> None:
        self.from_user = FakeUser(tg_id)
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:  # noqa: ANN003 — стаб: прочие опции Telegram игнорируем
        self.answers.append(text)


class FakeCommand:
    def __init__(self, args: str | None) -> None:
        self.args = args


class FakeMessageWithText(FakeMessage):
    """Сообщение юзера с текстом — источник для capture."""

    def __init__(self, tg_id: int, text: str) -> None:
        super().__init__(tg_id)
        self.text = text

    async def reply(self, text: str, **kwargs) -> None:
        self.answers.append(text)


class FakeBotMessage:
    """Сообщение бота с кнопками: то, что редактируется/удаляется в колбэке."""

    def __init__(self, source: FakeMessageWithText | None) -> None:
        self.reply_to_message = source
        self.edits: list[str] = []
        self.deleted = False

    async def edit_text(self, text: str, **kwargs) -> None:
        self.edits.append(text)

    async def delete(self) -> None:
        self.deleted = True


class FakeCallback:
    def __init__(
        self, data: str, tg_id: int, source: FakeMessageWithText | None
    ) -> None:
        self.data = data
        self.from_user = FakeUser(tg_id)
        self.message = FakeBotMessage(source)
        self.alerts: list[str] = []

    async def answer(self, text: str | None = None, **kwargs) -> None:
        if text:
            self.alerts.append(text)


class FakeBot:
    """Стаб aiogram Bot для notifier: копит send_message вместо похода в Telegram."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.sent.append((chat_id, text))


async def _next_handler(event, data):
    """Следующее звено цепочки middleware: отдаёт access, как его видит хендлер."""
    return data.get("access")


def auth_data(provider: TokenProvider, tg_id: int) -> dict:
    """data-словарь, каким его собирает aiogram для хендлера с flags={"auth": True}."""
    return {
        "handler": HandlerObject(callback=_next_handler, flags={"auth": True}),
        "event_from_user": FakeUser(tg_id),
        "token_provider": provider,
    }


async def cleanup() -> None:
    async with async_session() as session:
        await BotRepository(session).delete(TG_ID)


async def main() -> None:
    web = httpx.AsyncClient(base_url=setting.auth_url, timeout=5)
    bot_http = httpx.AsyncClient(base_url=setting.auth_url, timeout=5)
    provider = TokenProvider(bot_http, async_session, setting.access_ttl)

    await cleanup()

    email = f"e2e-bot-{int(time.time())}@test.io"
    password = "Passw0rd!e2e"

    print("== подготовка: register/login/link-code ==")
    r = await web.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert r.status_code == 201, f"register: {r.status_code} {r.text}"
    r = await web.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert r.status_code == 200, f"login: {r.status_code} {r.text}"
    web_access = web.cookies.get("cairn_token")  # auth сам ждёт Bearer, не cookie
    assert web_access, "access-cookie не пришла после login"
    web.headers["Authorization"] = f"Bearer {web_access}"
    r = await web.post("/api/v1/auth/link-code")
    assert r.status_code == 200, f"link-code: {r.status_code} {r.text}"
    code = r.json()["code"]
    print(f"  user={email}, code={code}")

    print("== 1. link с мусорным кодом -> InvalidCodeError ==")
    try:
        await provider.link(TG_ID, "000000")
        check("InvalidCodeError", False, "исключения не было")
    except InvalidCodeError:
        check("InvalidCodeError", True)

    print("== 2. link с настоящим кодом ==")
    await provider.link(TG_ID, code)
    async with async_session() as session:
        link_row = await BotRepository(session).get_by_telegram_id(TG_ID)
    check("строка в bot-db появилась", link_row is not None)
    refresh_v1 = link_row.refresh_token
    access_v1 = provider._cache[TG_ID][0]
    check("access в кэше", bool(access_v1))

    print("== 3. get_access из кэша (без сети) ==")
    access = await provider.get_access(TG_ID)
    check("вернулся закэшированный", access == access_v1)

    print("== 4. код одноразовый: повторный redeem -> InvalidCodeError ==")
    try:
        await provider.link(TG_ID, code)
        check("повторный redeem отбит", False, "исключения не было")
    except InvalidCodeError:
        check("повторный redeem отбит", True)

    print("== 5. просроченный кэш -> refresh + ротация ==")
    tok, _ = provider._cache[TG_ID]
    provider._cache[TG_ID] = (tok, time.monotonic() - 1)  # протухший дедлайн
    access_v2 = await provider.get_access(TG_ID)
    async with async_session() as session:
        link_row2 = await BotRepository(session).get_by_telegram_id(TG_ID)
    check("выдан новый access", access_v2 != "" and access_v2 is not None)
    check("refresh в БД сротирован", link_row2.refresh_token != refresh_v1)

    print("== 6. access живой: /me отвечает 200 ==")
    r = await bot_http.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_v2}"}
    )
    check(
        "/me == 200 и email совпал", r.status_code == 200 and r.json()["email"] == email
    )

    print("== 7. мёртвый refresh в БД -> 401 -> отвязка -> NotLinkedError ==")
    async with async_session() as session:
        await BotRepository(session).upsert(
            TG_ID,
            uuid.UUID(str(link_row2.user_id)),
            refresh_v1,  # старый, уже сротированный
        )
    provider._cache.pop(TG_ID, None)
    try:
        await provider.get_access(TG_ID)
        check("NotLinkedError после 401", False, "исключения не было")
    except NotLinkedError:
        check("NotLinkedError после 401", True)
    async with async_session() as session:
        gone = await BotRepository(session).get_by_telegram_id(TG_ID)
    check("строка удалена из bot-db", gone is None)

    print("== 8. AuthMiddleware без привязки -> NotLinkedError ==")
    # Токен теперь достаёт middleware; исключение из неё ловит errors-роутер
    try:
        await AuthMiddleware()(_next_handler, None, auth_data(provider, TG_ID))
        check("NotLinkedError долетела", False, "исключения не было")
    except NotLinkedError:
        check("NotLinkedError долетела", True)

    print("== 9. хендлер /start: без кода, с мусором, с настоящим кодом ==")
    msg = FakeMessage(TG_ID)
    await cmd_start(msg, FakeCommand(None), provider)  # type: ignore[arg-type]
    check(
        "подсказка при /start без кода",
        any("код возьми" in a for a in msg.answers),
        str(msg.answers),
    )

    msg = FakeMessage(TG_ID)
    await cmd_start(msg, FakeCommand("<abcdef>"), provider)  # type: ignore[arg-type]
    check(
        "мусорный код отбит",
        any("не подошёл" in a for a in msg.answers),
        str(msg.answers),
    )

    r = await web.post("/api/v1/auth/link-code")
    assert r.status_code == 200, f"link-code#2: {r.status_code} {r.text}"
    code2 = r.json()["code"]
    msg = FakeMessage(TG_ID)
    await cmd_start(msg, FakeCommand(f"<{code2}>"), provider)  # type: ignore[arg-type]
    check(
        "привязка через хендлер",
        any("привязан" in a for a in msg.answers),
        str(msg.answers),
    )

    print("== 10. AuthMiddleware выдаёт access, /whoami отвечает ==")
    access = await AuthMiddleware()(_next_handler, None, auth_data(provider, TG_ID))
    check("middleware выдала access", bool(access))
    msg = FakeMessage(TG_ID)
    await whoami(msg, access, bot_http)  # type: ignore[arg-type]
    check("отвечает email'ом", msg.answers == [email], str(msg.answers))

    main_http = httpx.AsyncClient(base_url=setting.main_api_url, timeout=10)

    print("== 11. /entries у свежего юзера — пусто ==")
    msg = FakeMessage(TG_ID)
    try:
        await cmd_entries(msg, access, main_http)  # type: ignore[arg-type]
        check(
            "«записей нет»", any("пока нет" in a for a in msg.answers), str(msg.answers)
        )
    except Exception as exc:  # noqa: BLE001 — e2e: показываем, чем упал хендлер
        check("«записей нет»", False, f"хендлер упал: {type(exc).__name__}: {exc}")

    print("== 12. /add и /note: подсказки без аргументов ==")
    msg = FakeMessage(TG_ID)
    await cmd_add(msg, FakeCommand(None), access, main_http)  # type: ignore[arg-type]
    check("подсказка /add", any("Так:" in a for a in msg.answers), str(msg.answers))
    msg = FakeMessage(TG_ID)
    await cmd_note(msg, FakeCommand(None), access, main_http)  # type: ignore[arg-type]
    check("подсказка /note", any("Так:" in a for a in msg.answers), str(msg.answers))

    print("== 13. /add <url> создаёт запись ==")
    msg = FakeMessage(TG_ID)
    try:
        await cmd_add(msg, FakeCommand("https://example.com/e2e"), access, main_http)  # type: ignore[arg-type]
        check("«добавил»", any("Добавил" in a for a in msg.answers), str(msg.answers))
    except Exception as exc:  # noqa: BLE001
        check("«добавил»", False, f"хендлер упал: {type(exc).__name__}: {exc}")

    print("== 14. /note <текст> создаёт заметку ==")
    msg = FakeMessage(TG_ID)
    try:
        await cmd_note(msg, FakeCommand("мысль из e2e-прогона"), access, main_http)  # type: ignore[arg-type]
        check("«записал»", any("Записал" in a for a in msg.answers), str(msg.answers))
    except Exception as exc:  # noqa: BLE001
        check("«записал»", False, f"хендлер упал: {type(exc).__name__}: {exc}")

    print("== 15. /entries показывает обе записи ==")
    msg = FakeMessage(TG_ID)
    try:
        await cmd_entries(msg, access, main_http)  # type: ignore[arg-type]
        text = "\n".join(msg.answers)
        check(
            "список с обеими записями",
            "example.com/e2e" in text and "мысль из e2e" in text,
            str(msg.answers),
        )
    except Exception as exc:  # noqa: BLE001
        check(
            "список с обеими записями",
            False,
            f"хендлер упал: {type(exc).__name__}: {exc}",
        )

    print("== 16. Kafka: уведомление привязанному владельцу ==")
    fake_bot = FakeBot()
    notifier_task = asyncio.create_task(run_notifier(fake_bot, async_session))  # type: ignore[arg-type]
    await asyncio.sleep(6)  # консьюмеру нужно вступить в группу и получить партиции

    access = await provider.get_access(TG_ID)
    resp = await main_http.post(
        "/api/v1/entries/",
        json={"title": "kafka-e2e", "type": "note", "content": "проверка уведомлений"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 201, f"create entry: {resp.status_code} {resp.text}"

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not fake_bot.sent:
        await asyncio.sleep(0.2)
    check(
        "уведомление пришло в правильный чат",
        any(
            chat_id == TG_ID and "добавлена запись" in text
            for chat_id, text in fake_bot.sent
        ),
        str(fake_bot.sent),
    )

    print("== 17. Kafka: непривязанный юзер — тишина ==")
    # Дожидаемся хвоста: события тестов 13–14 лежали в топике, пока у группы
    # bot-notifier не было консьюмера (compose-бот остановлен) — тест 16
    # выходит по первому сообщению, остальной бэклог доезжает позже.
    quiet_until = time.monotonic() + 3
    while time.monotonic() < quiet_until:
        n = len(fake_bot.sent)
        await asyncio.sleep(1)
        if len(fake_bot.sent) != n:
            quiet_until = time.monotonic() + 3
    sent_before = len(fake_bot.sent)
    web2 = httpx.AsyncClient(base_url=setting.auth_url, timeout=5)
    email2 = f"e2e-nolink-{int(time.time())}@test.io"
    r = await web2.post(
        "/api/v1/auth/register", json={"email": email2, "password": password}
    )
    assert r.status_code == 201, f"register#2: {r.status_code} {r.text}"
    r = await web2.post(
        "/api/v1/auth/login", json={"email": email2, "password": password}
    )
    assert r.status_code == 200, f"login#2: {r.status_code} {r.text}"
    # main-api принимает cookie (extract_token) — Bearer не нужен
    resp = await main_http.post(
        "/api/v1/entries/",
        json={"title": "no-link", "type": "note", "content": "не должно уведомить"},
        cookies=web2.cookies,
    )
    assert resp.status_code == 201, f"create entry#2: {resp.status_code} {resp.text}"
    await asyncio.sleep(5)  # даём консьюмеру время съесть событие
    check(
        "уведомлений не прибавилось",
        len(fake_bot.sent) == sent_before,
        str(fake_bot.sent),
    )
    await web2.aclose()

    notifier_task.cancel()
    try:
        await notifier_task
    except asyncio.CancelledError:
        pass

    print("== 18. capture: текст без команды -> кнопки ==")
    src = FakeMessageWithText(TG_ID, "просто мысль без команды")
    await catch_text(src)  # type: ignore[arg-type]
    check(
        "предложил сохранить",
        any("Что сохранить" in a for a in src.answers),
        str(src.answers),
    )

    print("== 19. колбэк save:note сохраняет заметку ==")
    cb = FakeCallback("save:note", TG_ID, src)
    await on_save(cb, access, main_http)  # type: ignore[arg-type]
    check(
        "сообщение отредактировано в «Сохранил»",
        "Сохранил ✅" in cb.message.edits,
        str(cb.message.edits),
    )

    print("== 20. колбэк save:link сохраняет ссылку ==")
    src2 = FakeMessageWithText(TG_ID, "https://example.com/capture-e2e")
    cb = FakeCallback("save:link", TG_ID, src2)
    await on_save(cb, access, main_http)  # type: ignore[arg-type]
    check("ссылка сохранена", "Сохранил ✅" in cb.message.edits, str(cb.message.edits))

    msg = FakeMessage(TG_ID)
    await cmd_entries(msg, access, main_http)  # type: ignore[arg-type]
    text = "\n".join(msg.answers)
    check(
        "обе появились в /entries",
        "просто мысль без команды" in text and "capture-e2e" in text,
        str(msg.answers),
    )

    print("== 21. колбэк save:cancel удаляет вопрос ==")
    cb = FakeCallback("save:cancel", TG_ID, src)
    await on_cancel(cb)  # type: ignore[arg-type]
    check("сообщение с кнопками удалено", cb.message.deleted)

    print("== 22. middleware для непривязанного юзера -> NotLinkedError ==")
    try:
        await AuthMiddleware()(_next_handler, None, auth_data(provider, 111_222))
        check("NotLinkedError долетела", False, "исключения не было")
    except NotLinkedError:
        check("NotLinkedError долетела", True)

    await main_http.aclose()
    await cleanup()
    await web.aclose()
    await bot_http.aclose()
    await engine.dispose()

    print(f"\nИтог: {passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
