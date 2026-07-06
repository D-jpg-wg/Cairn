from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SubscriptionRead(BaseModel):
    id: UUID
    feed_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionCreate(BaseModel):
    feed_url: str = Field(min_length=1, max_length=2048)

    model_config = {"str_strip_whitespace": True}
