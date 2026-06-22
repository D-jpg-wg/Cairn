import uuid

import jwt
from fastapi import HTTPException
from starlette import status

from app.core.config import setting

_ALGORITHM = "RS256"

# main-api только ПРОВЕРЯЕТ токены — нужен лишь публичный ключ auth-сервиса.
_PUBLIC_KEY = setting.jwt_public_key


def decode_access_token(token: str) -> uuid.UUID:
    """Проверяет подпись JWT публичным ключом и возвращает uuid пользователя (sub)."""
    try:
        payload = jwt.decode(token, _PUBLIC_KEY, algorithms=[_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
