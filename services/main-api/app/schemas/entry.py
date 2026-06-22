from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EntryRead(BaseModel):
    id: UUID
    title: str
    type: str
    content: str | None
    url: str | None
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class EntryCreate(BaseModel):
    title: str
    type: str
    content: str | None = None
    url: str | None = None


class EntryUpdate(BaseModel):
    title: str | None
    type: str | None
    content: str | None
    url: str | None
