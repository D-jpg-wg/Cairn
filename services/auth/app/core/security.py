from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError
from starlette import status

from app.core.config import setting

_ALGORITHM = "RS256"
_EXPIRE_DAYS = 7

# Ключи читаем один раз на старте: приватным подписываем, публичным проверяем.
_PRIVATE_KEY = setting.jwt_private_key
_PUBLIC_KEY = setting.jwt_public_key

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed_password: str) -> bool:
    try:
        return _ph.verify(hashed_password, plain)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def create_access_token(user_uuid: str) -> str:
    payload = {
        "sub": user_uuid,
        "exp": datetime.now(timezone.utc) + timedelta(days=_EXPIRE_DAYS),
    }
    return jwt.encode(
        payload,
        _PRIVATE_KEY,
        algorithm=_ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, _PUBLIC_KEY, algorithms=[_ALGORITHM])
        return payload["sub"]
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
