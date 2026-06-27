"""Интеграционные тесты auth поверх реального Postgres (testcontainers)."""

from urllib.parse import parse_qs, urlparse

API = "/api/v1/auth"
EMAIL = "user@example.com"
PASSWORD = "pass1234"


async def _register(client, email=EMAIL, password=PASSWORD):
    return await client.post(
        f"{API}/register", json={"email": email, "password": password}
    )


async def _login(client, email=EMAIL, password=PASSWORD):
    return await client.post(
        f"{API}/login", json={"email": email, "password": password}
    )


# ---------- регистрация / вход ----------


async def test_register_returns_user(client):
    r = await _register(client)
    assert r.status_code == 201
    assert r.json()["email"] == EMAIL


async def test_register_duplicate_email_conflicts(client):
    await _register(client)
    r = await _register(client)
    assert r.status_code == 409


async def test_login_sets_both_cookies(client):
    await _register(client)
    r = await _login(client)
    assert r.status_code == 200
    assert "cairn_token" in r.cookies
    assert "cairn_refresh" in r.cookies


async def test_login_wrong_password_unauthorized(client):
    await _register(client)
    r = await _login(client, password="nope")
    assert r.status_code == 401


# ---------- /me (Bearer) ----------


async def test_me_requires_token(client):
    r = await client.get(f"{API}/me")
    assert r.status_code in (401, 403)


async def test_me_returns_current_user(client):
    await _register(client)
    await _login(client)
    token = client.cookies.get("cairn_token")
    r = await client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


# ---------- жизненный цикл refresh ----------


async def test_refresh_rotates_and_invalidates_old(client):
    await _register(client)
    await _login(client)
    old_refresh = client.cookies.get("cairn_refresh")

    r = await client.post(f"{API}/refresh")
    assert r.status_code == 200
    new_refresh = client.cookies.get("cairn_refresh")
    assert new_refresh and new_refresh != old_refresh

    # старый refresh после ротации не принимается
    client.cookies.clear()
    client.cookies.set("cairn_refresh", old_refresh)
    r_old = await client.post(f"{API}/refresh")
    assert r_old.status_code == 401


async def test_logout_revokes_refresh(client):
    await _register(client)
    await _login(client)
    refresh = client.cookies.get("cairn_refresh")

    r = await client.post(f"{API}/logout")
    assert r.status_code == 204

    client.cookies.clear()
    client.cookies.set("cairn_refresh", refresh)
    r_after = await client.post(f"{API}/refresh")
    assert r_after.status_code == 401


async def test_refresh_without_cookie_unauthorized(client):
    r = await client.post(f"{API}/refresh")
    assert r.status_code == 401


# ---------- Google OAuth (внешний вызов замокан) ----------


async def test_google_oauth_flow_issues_session(client):
    from app.api.auth import get_google_oauth
    from app.main import app

    class FakeGoogle:
        def build_authorization_url(self, state):
            return f"https://accounts.google.test/auth?state={state}"

        async def fetch_email(self, code):
            return "oauth@example.com"

    app.dependency_overrides[get_google_oauth] = lambda: FakeGoogle()
    try:
        start = await client.get(f"{API}/oauth/google", follow_redirects=False)
        assert start.status_code in (302, 307)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]

        cb = await client.get(
            f"{API}/oauth/google/callback?code=fake&state={state}",
            follow_redirects=False,
        )
        assert cb.status_code in (302, 307)
        assert "cairn_token" in cb.cookies
        assert "cairn_refresh" in cb.cookies
    finally:
        app.dependency_overrides.pop(get_google_oauth, None)


async def test_google_oauth_bad_state_rejected(client):
    cb = await client.get(
        f"{API}/oauth/google/callback?code=fake&state=forged",
        follow_redirects=False,
    )
    assert cb.status_code == 400
