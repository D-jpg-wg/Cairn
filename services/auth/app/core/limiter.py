from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse

# key_func решает, "по кому" считать лимит. get_remote_address = по IP клиента.
limiter = Limiter(key_func=get_remote_address)


async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """Ответ на превышение лимита в едином формате."""
    limit = exc.detail if isinstance(exc, RateLimitExceeded) else "exceeded"
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": f"Too many requests, limit: {limit}"},
    )
