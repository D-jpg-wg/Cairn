"""Контракт доверия к токену: main-api принимает только валидно подписанный JWT."""

from datetime import timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ME = "/api/v1/me"


async def test_valid_token_accepted(client, auth, user_a):
    r = await client.get(ME, headers=auth(user_a))
    assert r.status_code == 200
    assert r.json()["user_id"] == user_a


async def test_no_token_unauthorized(client):
    r = await client.get(ME)
    assert r.status_code == 401


async def test_garbage_token_unauthorized(client):
    r = await client.get(ME, headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


async def test_token_signed_by_wrong_key_rejected(client, make_jwt, user_a):
    # Чужой приватный ключ — подпись не сойдётся с публичным ключом main-api.
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    forged = make_jwt(user_a, key=other_pem)
    r = await client.get(ME, headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


async def test_expired_token_rejected(client, make_jwt, user_a):
    expired = make_jwt(user_a, exp=timedelta(minutes=-1))
    r = await client.get(ME, headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


async def test_token_via_cookie_accepted(client, make_jwt, user_a):
    # main-api берёт токен и из cookie cairn_token, не только из заголовка.
    client.cookies.set("cairn_token", make_jwt(user_a))
    r = await client.get(ME)
    assert r.status_code == 200
    assert r.json()["user_id"] == user_a
