import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UUID, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Subscription(Base):
    """Подписка юзера на ленту: консьюмер page.parsed раздаёт записи по ней."""

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "feed_url"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID, index=True)
    feed_url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
