"""Unit-тесты чистых функций безопасности (БД не нужна)."""

import uuid

import pytest
from fastapi import HTTPException

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_refresh_token_hash_is_stable_and_not_reversible():
    raw = generate_refresh_token()
    assert hash_refresh_token(raw) == hash_refresh_token(raw)  # детерминирован
    assert hash_refresh_token(raw) != raw  # в БД хранится не сырой токен


def test_access_token_roundtrip():
    uid = str(uuid.uuid4())
    token = create_access_token(uid)
    assert decode_access_token(token) == uid


def test_decode_invalid_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        decode_access_token("not-a-jwt")
    assert exc.value.status_code == 401
