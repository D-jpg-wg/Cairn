from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from sqlalchemy import select

from app.db.sync_session import SyncSession
from app.models.entry import Entry, EntryStatus, ENRICHABLE_TYPES
from app.services.enrich import extract_from_url
from app.worker.celery_app import celery_app


_STUCK_AFTER = timedelta(minutes=2)
_SWEEP_BATCH = 50


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def enrich_entry(self, entry_id: str) -> None:
    """Фоновое обогащение: тянет контент по URL, ставит ready/failed."""
    with SyncSession() as session:
        entry = session.get(Entry, UUID(entry_id))
        if entry is None or not entry.url:
            return  # запись удалили или у неё нет URL — тихий no-op

        try:
            _title, text = extract_from_url(entry.url)
        except httpx.HTTPError as exc:
            if self.request.retries >= self.max_retries:
                entry.status = EntryStatus.FAILED
                session.commit()
                return
            raise self.retry(exc=exc)
        except ValueError:
            entry.status = EntryStatus.FAILED
            session.commit()
            return

        entry.content = text
        entry.status = EntryStatus.READY
        session.commit()


@celery_app.task
def sweep_stuck_pending() -> int:
    """Подбирает зависшие pending (старше порога) и заново ставит их обогащение."""
    cutoff = datetime.now(timezone.utc) - _STUCK_AFTER
    with SyncSession() as session:
        stuck_ids = (
            session.execute(
                select(Entry.id)
                .where(
                    Entry.status == EntryStatus.PENDING,
                    Entry.type.in_(ENRICHABLE_TYPES),
                    Entry.created_at < cutoff,
                )
                .limit(_SWEEP_BATCH)
            )
            .scalars()
            .all()
        )
    for entry_id in stuck_ids:
        enrich_entry.delay(str(entry_id))
    return len(stuck_ids)
