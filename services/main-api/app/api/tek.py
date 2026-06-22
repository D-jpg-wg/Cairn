import uuid
from fastapi import Depends, APIRouter
from app.core.deps import get_current_user_id

router = APIRouter()


@router.get("/api/v1/whoami")
def whoami(owner_id: uuid.UUID = Depends(get_current_user_id)):
    return {"owner_id": str(owner_id)}
