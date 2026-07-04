from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.security import decode_access_token
from app.core.tokens import ACCESS_COOKIE
from app.db.db_engine import get_async_session
from app.models import User
from app.repositories.user_repository import AuthRepository


def _extract_token(request: Request) -> str | None:
    """Токен сначала в cookie (браузер, httponly), затем в Authorization: Bearer
    (бот и другие машинные клиенты). Тот же порядок, что в main-api."""
    token = request.cookies.get(ACCESS_COOKIE)
    if token:
        return token
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header.removeprefix("Bearer ").strip()
    return None


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    user_uuid = decode_access_token(token)
    user = await AuthRepository(session).get_by_uuid(str(user_uuid))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return user
