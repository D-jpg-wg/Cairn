"""CRUD записей и — главное — изоляция владельца (юзер видит только своё)."""

ENTRIES = "/api/v1/entries/"


async def _create(client, headers, **kw):
    payload = {"title": "Заметка", "type": "note", "content": "тело", "tags": [], **kw}
    return await client.post(ENTRIES, json=payload, headers=headers)


# ---------- базовый CRUD ----------


async def test_create_entry(client, auth, user_a):
    r = await _create(client, auth(user_a), title="Первая")
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Первая"
    assert (
        body["status"] == "ready"
    )  # note без URL — контент уже есть, обогащать нечего


async def test_list_returns_created(client, auth, user_a):
    await _create(client, auth(user_a))
    r = await client.get(ENTRIES, headers=auth(user_a))
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_get_by_id(client, auth, user_a):
    created = (await _create(client, auth(user_a))).json()
    r = await client.get(f"{ENTRIES}{created['id']}", headers=auth(user_a))
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


async def test_update_entry(client, auth, user_a):
    created = (await _create(client, auth(user_a))).json()
    r = await client.patch(
        f"{ENTRIES}{created['id']}", json={"title": "Новый"}, headers=auth(user_a)
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Новый"


async def test_delete_entry(client, auth, user_a):
    created = (await _create(client, auth(user_a))).json()
    r = await client.delete(f"{ENTRIES}{created['id']}", headers=auth(user_a))
    assert r.status_code == 204
    r2 = await client.get(f"{ENTRIES}{created['id']}", headers=auth(user_a))
    assert r2.status_code == 404


async def test_get_missing_returns_404(client, auth, user_a):
    import uuid

    r = await client.get(f"{ENTRIES}{uuid.uuid4()}", headers=auth(user_a))
    assert r.status_code == 404


# ---------- изоляция владельца (безопасность) ----------


async def test_user_sees_only_own_entries(client, auth, user_a, user_b):
    await _create(client, auth(user_a), title="A")
    await _create(client, auth(user_b), title="B")

    list_a = (await client.get(ENTRIES, headers=auth(user_a))).json()
    list_b = (await client.get(ENTRIES, headers=auth(user_b))).json()
    assert [e["title"] for e in list_a] == ["A"]
    assert [e["title"] for e in list_b] == ["B"]


async def test_cannot_read_others_entry(client, auth, user_a, user_b):
    created = (await _create(client, auth(user_a))).json()
    r = await client.get(f"{ENTRIES}{created['id']}", headers=auth(user_b))
    assert r.status_code == 404  # чужая запись для B как несуществующая


async def test_cannot_update_others_entry(client, auth, user_a, user_b):
    created = (await _create(client, auth(user_a))).json()
    r = await client.patch(
        f"{ENTRIES}{created['id']}", json={"title": "hacked"}, headers=auth(user_b)
    )
    assert r.status_code == 404


async def test_cannot_delete_others_entry(client, auth, user_a, user_b):
    created = (await _create(client, auth(user_a))).json()
    r = await client.delete(f"{ENTRIES}{created['id']}", headers=auth(user_b))
    assert r.status_code == 404
    # запись на месте у владельца
    assert (
        await client.get(f"{ENTRIES}{created['id']}", headers=auth(user_a))
    ).status_code == 200


# ---------- валидация типов ----------


async def test_link_without_url_rejected(client, auth, user_a):
    r = await _create(client, auth(user_a), type="link", content=None, url=None)
    assert r.status_code == 422


async def test_note_without_content_rejected(client, auth, user_a):
    r = await _create(client, auth(user_a), type="note", content=None)
    assert r.status_code == 422
