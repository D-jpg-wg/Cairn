from fastapi import HTTPException
from starlette import status

from app.core.security import hash_password, verify_password, create_access_token
from app.models import User
from app.repositories.user_repository import AuthRepository
from app.schemas.user import UserCreate, LoginRequest, TokenResponse


class AuthService:
    """"""

    def __init__(self, repo: AuthRepository) -> None:
        self.repo = repo

    async def register(self, body: UserCreate) -> User:
        if await self.repo.get_by_email(body.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
            )

        return await self.repo.create(
            email=body.email, hashed_password=hash_password(body.password)
        )

    async def login(self, body: LoginRequest) -> TokenResponse:
        user = await self.repo.get_by_email(body.email)
        if not user or not verify_password(body.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        return TokenResponse(access_token=create_access_token(str(user.uuid)))
