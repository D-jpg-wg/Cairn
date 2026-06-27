from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status
from starlette.responses import Response

from app.core.deps import _COOKIE_NAME, get_current_user_id

router = APIRouter()


@router.get("/me")
async def me(user_id: UUID = Depends(get_current_user_id)) -> dict:
    """Подтверждает, что пользователь аутентифицирован валидным JWT auth-сервиса.

    Email недоступен: пользователи живут в auth-сервисе (database-per-service),
    здесь из подписанного токена доступен только его uuid (sub).
    """
    return {"authenticated": True, "user_id": str(user_id)}


@router.post("/logout")
async def logout() -> Response:
    """Удаляет cookie с токеном (удобно для повторного теста входа)."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(_COOKIE_NAME)
    return response
