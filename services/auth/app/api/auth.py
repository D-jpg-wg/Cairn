import secrets

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import RedirectResponse

from app.core.config import setting
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.db.db_engine import get_async_session
from app.models import User
from app.repositories.user_repository import AuthRepository
from app.schemas.user import UserCreate, LoginRequest, UserRead, TokenResponse
from app.services.auth_service import AuthService
from app.services.google_oauth import GoogleOAuthClient

_OAUTH_STATE_KEY = "oauth_state"

router = APIRouter()


def get_auth_service(session: AsyncSession = Depends(get_async_session)) -> AuthService:
    return AuthService(AuthRepository(session))


def get_google_oauth() -> GoogleOAuthClient:
    return GoogleOAuthClient()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: UserCreate,
    service: AuthService = Depends(get_auth_service),
):
    return await service.register(body)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.login(body)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/oauth/google")
async def google_login(
    request: Request,
    google: GoogleOAuthClient = Depends(get_google_oauth),
):
    state = secrets.token_urlsafe(16)
    request.session[_OAUTH_STATE_KEY] = state
    return RedirectResponse(google.build_authorization_url(state))


@router.get("/oauth/google/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str,
    service: AuthService = Depends(get_auth_service),
    google: GoogleOAuthClient = Depends(get_google_oauth),
):
    expected_state = request.session.pop(_OAUTH_STATE_KEY, None)
    if not expected_state or state != expected_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state"
        )

    email = await google.fetch_email(code)
    token = await service.login_oauth(email)

    resp = RedirectResponse(url="/")
    resp.set_cookie(
        "cairn_token",
        token.access_token,
        httponly=True,
        secure=setting.cookie_secure,
        samesite="lax",
    )
    return resp
