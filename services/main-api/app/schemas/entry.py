from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator, Field

from app.models.entry import EntryType, EntryStatus
from app.schemas.tag import TagRead


def _normalize_tags(tags: list[str]) -> list[str]:
    seen = {}
    for tag in tags:
        tag = tag.strip().lower()
        if tag:
            seen.setdefault(tag, None)
    return list(seen)


class EntryRead(BaseModel):
    id: UUID
    title: str
    type: EntryType
    content: str | None
    url: str | None
    status: EntryStatus
    created_at: datetime
    tags: list[TagRead] = []

    model_config = {"from_attributes": True}


class EntryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    type: EntryType
    content: str | None = None
    url: str | None = Field(default=None, max_length=2048)
    tags: list[str] = []

    model_config = {"str_strip_whitespace": True}

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        return _normalize_tags(tags)

    @model_validator(mode="after")
    def check_type_payload(self):
        if (
            self.type in {EntryType.LINK, EntryType.ARTICLE, EntryType.VIDEO}
            and not self.url
        ):
            raise ValueError(f"{self.type.value} requires url")
        if self.type in {EntryType.NOTE, EntryType.SNIPPET} and not self.content:
            raise ValueError(f"{self.type.value} requires content")
        return self


class EntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    type: EntryType | None = None
    content: str | None = None
    url: str | None = Field(default=None, max_length=2048)
    tags: list[str] | None = None

    model_config = {"str_strip_whitespace": True}

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str] | None) -> list[str] | None:
        if tags is None:
            return None
        return _normalize_tags(tags)
