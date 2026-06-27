from uuid import UUID

from fastapi import HTTPException, Request
from starlette import status

from app.core.security import decode_access_token

COOKIE_NAME = "cairn_token"


def extract_token(request: Request) -> str | None:
    """Токен ищем сначала в cookie (его ставит auth после OAuth-входа),
    затем в заголовке Authorization: Bearer ..."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.removeprefix("Bearer ").strip()
    return None


def get_current_user_id(request: Request) -> UUID:
    """uuid пользователя из проверенного JWT.

    В БД не ходим: пользователи живут в auth-сервисе (database-per-service),
    доверяем подписанному токену. Это и есть owner_id для записей.
    """
    token = extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return decode_access_token(token)
