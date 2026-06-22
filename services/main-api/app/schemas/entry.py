from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.entry import EntryType, EntryStatus


class EntryRead(BaseModel):
    id: UUID
    title: str
    type: EntryType
    content: str | None
    url: str | None
    status: EntryStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class EntryCreate(BaseModel):
    title: str
    type: EntryType
    content: str | None = None
    url: str | None = None


class EntryUpdate(BaseModel):
    title: str | None = None
    type: EntryType | None = None
    content: str | None = None
    url: str | None = None
