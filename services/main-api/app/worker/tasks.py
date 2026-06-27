from uuid import UUID

import httpx

from app.db.sync_session import SyncSession
from app.models.entry import Entry, EntryStatus
from app.services.enrich import extract_from_url
from app.worker.celery_app import celery_app


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
