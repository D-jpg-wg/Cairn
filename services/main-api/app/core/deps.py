import uuid

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token

_bearer = HTTPBearer()


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    """uuid пользователя из проверенного JWT.

    В БД не ходим: пользователи живут в auth-сервисе (database-per-service),
    доверяем подписанному токену. Это и есть owner_id для записей.
    """
    return decode_access_token(credentials.credentials)
