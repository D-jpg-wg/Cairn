"""Тесты фонового обогащения: экстрактор, задача и постановка в очередь.

Всё без сети и без живого воркера/Redis: httpx и extract_from_url мокаются,
задача гоняется локально через .apply(), а .delay() подменяется.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.entry import Entry, EntryStatus, EntryType
from app.services.enrich import extract_from_url
from app.worker.tasks import enrich_entry, sweep_stuck_pending

ENTRIES = "/api/v1/entries/"


# ---------- экстрактор (мок httpx, без сети) ----------


class _FakeResp:
    def __init__(self, text: str, content_type: str = "text/html") -> None:
        self.text = text
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        pass


def _patch_httpx(monkeypatch, resp: _FakeResp) -> None:
    class _FakeClient:
        def __init__(self, **kw): ...
        def __enter__(self):
            return self

        def __exit__(self, *a): ...
        def get(self, url):
            return resp

    monkeypatch.setattr("app.services.enrich.httpx.Client", _FakeClient)


def test_extract_success(monkeypatch):
    html = "<html><head><title>Hi</title></head><body><script>JUNK</script><p>Hello</p></body></html>"
    _patch_httpx(monkeypatch, _FakeResp(html))
    title, text = extract_from_url("http://x")
    assert title == "Hi"
    assert "Hello" in text
    assert "JUNK" not in text  # содержимое <script> вырезано


def test_extract_non_html_raises(monkeypatch):
    _patch_httpx(monkeypatch, _FakeResp("", content_type="application/pdf"))
    with pytest.raises(ValueError):
        extract_from_url("http://x")


# ---------- задача (тестовая БД через task_db, extract замокан) ----------


def _seed(session, **kw) -> object:
    entry = Entry(
        id=uuid4(),
        owner_id=uuid4(),
        type=EntryType.LINK,
        title="t",
        url="http://x",
        status=EntryStatus.PENDING,
        **kw,
    )
    session.add(entry)
    session.commit()
    return entry.id


def test_task_marks_ready(task_db, monkeypatch):
    with task_db() as s:
        eid = _seed(s)
    monkeypatch.setattr("app.worker.tasks.extract_from_url", lambda url: ("T", "тело"))

    enrich_entry.apply(args=[str(eid)])

    with task_db() as s:
        entry = s.get(Entry, eid)
        assert entry.status == EntryStatus.READY
        assert entry.content == "тело"


def test_task_marks_failed_on_value_error(task_db, monkeypatch):
    with task_db() as s:
        eid = _seed(s)

    def boom(url):
        raise ValueError("not html")

    monkeypatch.setattr("app.worker.tasks.extract_from_url", boom)

    enrich_entry.apply(args=[str(eid)])

    with task_db() as s:
        assert s.get(Entry, eid).status == EntryStatus.FAILED


def test_task_noop_when_missing(task_db):
    result = enrich_entry.apply(args=[str(uuid4())])  # записи нет
    assert result.successful()  # задача не падает


def test_sweep_reenqueues_only_old_pending(task_db, monkeypatch):
    old = datetime.now(timezone.utc) - timedelta(minutes=5)
    fresh = datetime.now(timezone.utc)
    with task_db() as s:
        old_id = _seed(s, created_at=old)  # зависла давно — должна попасть
        _seed(s, created_at=fresh)  # свежая — в полёте, не трогаем

    calls = []
    monkeypatch.setattr(
        "app.worker.tasks.enrich_entry.delay", lambda eid: calls.append(eid)
    )

    n = sweep_stuck_pending.apply().get()

    assert n == 1
    assert calls == [str(old_id)]  # только старую


# ---------- постановка в очередь при создании (мок .delay, без Redis) ----------


async def test_create_link_enqueues(client, auth, user_a, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.services.entry_service.enrich_entry.delay", lambda eid: calls.append(eid)
    )
    r = await client.post(
        ENTRIES,
        headers=auth(user_a),
        json={"title": "L", "type": "link", "url": "http://x", "tags": []},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert calls == [r.json()["id"]]


async def test_create_note_no_enqueue_and_ready(client, auth, user_a, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.services.entry_service.enrich_entry.delay", lambda eid: calls.append(eid)
    )
    r = await client.post(
        ENTRIES,
        headers=auth(user_a),
        json={"title": "N", "type": "note", "content": "c", "tags": []},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "ready"
    assert calls == []
