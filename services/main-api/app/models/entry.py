import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Table,
    Text,
    UUID,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.tag import Tag


class EntryType(str, enum.Enum):
    """Вид записи. Определяет, что лежит в url/content и кто их заполняет."""

    NOTE = "note"  # заметка руками: content есть сразу, url пустой
    LINK = "link"  # закладка: url есть, content — описание или null
    ARTICLE = "article"  # спарсенная статья: url + извлечённый текст в content
    VIDEO = "video"  # видео (YouTube): url + транскрипт в content
    SNIPPET = "snippet"  # код-сниппет: content = код, url опционален


class EntryStatus(str, enum.Enum):
    """Стадия обогащения. content наполняется фоном (parser), отсюда статусы."""

    PENDING = "pending"  # создана, content ещё не извлечён
    READY = "ready"  # content готов, можно индексировать/искать
    FAILED = "failed"  # обогащение не удалось


# values_callable — чтобы в БД хранились значения ("note"), а не имена ("NOTE").
_entry_type = Enum(
    EntryType, name="entry_type", values_callable=lambda e: [m.value for m in e]
)
_entry_status = Enum(
    EntryStatus, name="entry_status", values_callable=lambda e: [m.value for m in e]
)


entry_tags = Table(
    "entry_tags",
    Base.metadata,
    Column(
        "entry_id", UUID, ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("tag_id", UUID, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    # Логическая ссылка на пользователя из auth-сервиса — без FK (другая БД).
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID, index=True)
    type: Mapped[EntryType] = mapped_column(_entry_type)
    status: Mapped[EntryStatus] = mapped_column(
        _entry_status,
        default=EntryStatus.PENDING,
        server_default=EntryStatus.PENDING.value,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tags: Mapped[list["Tag"]] = relationship(
        secondary=entry_tags, back_populates="entries"
    )
