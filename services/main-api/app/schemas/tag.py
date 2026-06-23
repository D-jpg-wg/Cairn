from uuid import UUID

from pydantic import BaseModel


class TagRead(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}
