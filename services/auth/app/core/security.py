from datetime import datetime, timezone

import hashlib
import secrets
import jwt
from fastapi import HTTPException
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError
from starlette import status

from app.core.config import setting
from app.core.tokens import ACCESS_TTL

_ALGORITHM = "RS256"

# Ключи читаем один раз на старте: приватным подписываем, публичным проверяем.
_PRIVATE_KEY = setting.jwt_private_key
_PUBLIC_KEY = setting.jwt_public_key

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    """Хэширует пароль (argon2) для хранения в БД."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed_password: str) -> bool:
    """Проверяет пароль против сохранённого хэша; False при несовпадении."""
    try:
        return _ph.verify(hashed_password, plain)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def create_access_token(user_uuid: str) -> str:
    """Подписывает короткоживущий JWT (RS256) с uuid пользователя в sub."""
    payload = {
        "sub": user_uuid,
        "exp": datetime.now(timezone.utc) + ACCESS_TTL,
    }
    return jwt.encode(
        payload,
        _PRIVATE_KEY,
        algorithm=_ALGORITHM,
    )


def generate_refresh_token() -> str:
    """Генерирует случайный refresh-токен (отдаётся клиенту в сыром виде)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw: str) -> str:
    """Хэширует refresh-токен (sha256) — в БД хранится только хэш."""
    return hashlib.sha256(raw.encode()).hexdigest()


def decode_access_token(token: str) -> str:
    """Проверяет подпись JWT публичным ключом и возвращает sub; 401 при ошибке."""
    try:
        payload = jwt.decode(token, _PUBLIC_KEY, algorithms=[_ALGORITHM])
        return payload["sub"]
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
