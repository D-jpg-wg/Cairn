import uuid

from sqlalchemy import BigInteger, UUID, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TelegramLink(Base):
    __tablename__ = "telegram_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, unique=True, index=True)
    refresh_token: Mapped[str] = mapped_column(String(128))
