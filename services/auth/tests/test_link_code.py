"""Интеграционные тесты привязки бота по одноразовому коду (link-code).

Сценарий: залогиненный юзер выпускает код (`/link-code`), бот меняет его на пару
токенов (`/link-code/redeem`). Код одноразовый и короткоживущий.
"""

from datetime import timedelta

API = "/api/v1/auth"
EMAIL = "link@example.com"
PASSWORD = "pass1234"


async def _auth_token(client, email=EMAIL, password=PASSWORD) -> str:
    """Регистрирует и логинит юзера, отдаёт его access-токен (из cookie)."""
    await client.post(f"{API}/register", json={"email": email, "password": password})
    await client.post(f"{API}/login", json={"email": email, "password": password})
    return client.cookies.get("cairn_token")


async def _issue_code(client, token: str) -> str:
    """Выпускает одноразовый код от имени залогиненного юзера."""
    r = await client.post(
        f"{API}/link-code", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    return r.json()["code"]


# ---------- выпуск кода (/link-code) ----------


async def test_link_code_requires_auth(client):
    # без Bearer выпустить код нельзя — код привязывается к конкретному юзеру
    r = await client.post(f"{API}/link-code")
    assert r.status_code in (401, 403)


async def test_link_code_returns_code(client):
    token = await _auth_token(client)
    r = await client.post(
        f"{API}/link-code", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json()["code"]


# ---------- размен кода (/link-code/redeem) ----------


async def test_redeem_returns_working_token_pair(client):
    token = await _auth_token(client)
    code = await _issue_code(client, token)

    r = await client.post(f"{API}/link-code/redeem", json={"code": code})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]

    # выданный access реально пускает в auth (тот же юзер) — как им воспользуется бот
    me = await client.get(
        f"{API}/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL
    # user_id в ответе — тот самый юзер: по нему бот запишет привязку telegram_id↔user_id
    assert body["user_id"] == me.json()["uuid"]


async def test_redeem_is_single_use(client):
    token = await _auth_token(client)
    code = await _issue_code(client, token)

    first = await client.post(f"{API}/link-code/redeem", json={"code": code})
    assert first.status_code == 200

    # повторный размен того же кода отбивается — одноразовость (used=True)
    second = await client.post(f"{API}/link-code/redeem", json={"code": code})
    assert second.status_code == 401


async def test_redeem_unknown_code_unauthorized(client):
    r = await client.post(f"{API}/link-code/redeem", json={"code": "no-such-code"})
    assert r.status_code == 401


async def test_redeem_expired_code_unauthorized(client, monkeypatch):
    # выпускаем код с уже истёкшим сроком: подменяем TTL на отрицательный
    monkeypatch.setattr(
        "app.services.auth_service.LINK_CODE_TTL", timedelta(seconds=-1)
    )
    token = await _auth_token(client)
    code = await _issue_code(client, token)

    r = await client.post(f"{API}/link-code/redeem", json={"code": code})
    assert r.status_code == 401


# ---------- JSON-рефреш (/token/refresh) ----------


async def _redeem_tokens(client) -> dict:
    """Полный путь бота: регистрация → код → redeem; отдаёт тело ответа redeem."""
    token = await _auth_token(client)
    code = await _issue_code(client, token)
    r = await client.post(f"{API}/link-code/redeem", json={"code": code})
    assert r.status_code == 200
    return r.json()


async def test_token_refresh_returns_new_pair(client):
    old = await _redeem_tokens(client)

    r = await client.post(
        f"{API}/token/refresh", json={"refresh_token": old["refresh_token"]}
    )
    assert r.status_code == 200
    new = r.json()

    # ротация: refresh обязан смениться — бот перезапишет его у себя в БД
    assert new["refresh_token"] != old["refresh_token"]
    assert new["user_id"] == old["user_id"]

    # новый access рабочий — им бот продолжит ходить в API
    me = await client.get(
        f"{API}/me", headers={"Authorization": f"Bearer {new['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL


async def test_token_refresh_rotates_and_invalidates_old(client):
    old = await _redeem_tokens(client)

    first = await client.post(
        f"{API}/token/refresh", json={"refresh_token": old["refresh_token"]}
    )
    assert first.status_code == 200

    # старый refresh погашен ротацией — если бот не сохранил новый, он отвязан
    second = await client.post(
        f"{API}/token/refresh", json={"refresh_token": old["refresh_token"]}
    )
    assert second.status_code == 401


async def test_token_refresh_unknown_token_unauthorized(client):
    r = await client.post(f"{API}/token/refresh", json={"refresh_token": "garbage"})
    assert r.status_code == 401
