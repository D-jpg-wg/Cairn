from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.deps import get_current_user
from app.db.db_engine import get_async_session
from app.models import User
from app.repositories.user_repository import AuthRepository
from app.schemas.user import UserCreate, LoginRequest, UserRead, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter()


def get_auth_service(session: AsyncSession = Depends(get_async_session)) -> AuthService:
    return AuthService(AuthRepository(session))


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, service: AuthService = Depends(get_auth_service)):
    return await service.register(body)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.login(body)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
