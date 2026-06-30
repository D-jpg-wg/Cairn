import secrets

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import JSONResponse, RedirectResponse, Response

from app.core.config import setting
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.core.tokens import (
    ACCESS_COOKIE,
    ACCESS_TTL,
    OAUTH_STATE_KEY,
    REFRESH_COOKIE,
    REFRESH_PATH,
    REFRESH_TTL,
)
from app.db.db_engine import get_async_session
from app.models import User
from app.repositories.user_repository import AuthRepository
from app.schemas.user import (
    UserCreate,
    LoginRequest,
    UserRead,
    LinkCodeResponse,
    LinkCodeRedeem,
    TokenPairResponse,
)
from app.services.auth_service import AuthService
from app.services.google_oauth import GoogleOAuthClient

router = APIRouter()


def _set_auth_cookie(response: Response, access: str, refresh: str) -> None:
    """Ставит httponly-cookie с access (короткий) и refresh (длинный, на auth-путь)."""
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        httponly=True,
        secure=setting.cookie_secure,
        samesite="lax",
        max_age=int(ACCESS_TTL.total_seconds()),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        secure=setting.cookie_secure,
        samesite="lax",
        max_age=int(REFRESH_TTL.total_seconds()),
        path=REFRESH_PATH,
    )


def get_auth_service(session: AsyncSession = Depends(get_async_session)) -> AuthService:
    """Зависимость: собирает AuthService поверх сессии БД."""
    return AuthService(AuthRepository(session))


def get_google_oauth() -> GoogleOAuthClient:
    """Зависимость: клиент Google OAuth 2.0."""
    return GoogleOAuthClient()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: UserCreate,
    service: AuthService = Depends(get_auth_service),
):
    """Регистрирует нового пользователя по email и паролю."""
    return await service.register(body)


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    """Проверяет пароль и выдаёт пару токенов в cookie."""
    access, refresh = await service.login(body)
    resp = JSONResponse({"ok": True})
    _set_auth_cookie(resp, access, refresh)
    return resp


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """Возвращает текущего пользователя по access-токену."""
    return current_user


@router.post("/link-code", response_model=LinkCodeResponse)
@limiter.limit("5/minute")
async def create_link_code(
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    """Залогиненный юзер получает одноразовый код для привязки Telegram-бота."""
    code = await service.create_link_code(current_user)
    return LinkCodeResponse(code=code)


@router.post("/link-code/redeem", response_model=TokenPairResponse)
@limiter.limit("10/minute")
async def redeem_link_code(
    request: Request,
    body: LinkCodeRedeem,
    service: AuthService = Depends(get_auth_service),
):
    """Бот меняет одноразовый код на пару токенов (JSON, not cookie)."""
    access, refresh = await service.redeem_link_code(body.code)
    return TokenPairResponse(access_token=access, refresh_token=refresh)


@router.get("/oauth/google")
async def google_login(
    request: Request,
    google: GoogleOAuthClient = Depends(get_google_oauth),
):
    """Начинает вход через Google: кладёт state в сессию и редиректит на Google."""
    state = secrets.token_urlsafe(16)
    request.session[OAUTH_STATE_KEY] = state
    return RedirectResponse(google.build_authorization_url(state))


@router.get("/oauth/google/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str,
    service: AuthService = Depends(get_auth_service),
    google: GoogleOAuthClient = Depends(get_google_oauth),
):
    """Callback Google: сверяет state, логинит/создаёт юзера, ставит cookie и редиректит в приложение."""
    expected_state = request.session.pop(OAUTH_STATE_KEY, None)
    if not expected_state or state != expected_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state"
        )

    email = await google.fetch_email(code)
    access, refresh = await service.login_oauth(email)

    resp = RedirectResponse(url=setting.app_url)
    _set_auth_cookie(resp, access, refresh)
    return resp


@router.post("/refresh")
async def refresh_tokens(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    """Обменивает refresh-cookie на новую пару токенов (с ротацией старого refresh)."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token"
        )

    access, refresh = await service.refresh(raw)
    resp = JSONResponse({"ok": True})
    _set_auth_cookie(resp, access, refresh)
    return resp


@router.post("/logout")
async def logout(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    """Отзывает refresh в БД и удаляет обе cookie."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        await service.logout(raw)
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(ACCESS_COOKIE)
    resp.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    return resp
