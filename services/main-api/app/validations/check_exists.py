from typing import Optional

from fastapi import HTTPException
from starlette import status

from app.models import Entry


def check_exists_entry(obj: Optional[Entry]) -> Entry:
    """Возвращает запись либо бросает 404, если её нет."""
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
        )
    return obj
