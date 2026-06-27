from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness-проба: сервис жив."""
    return {"status": "ok"}
