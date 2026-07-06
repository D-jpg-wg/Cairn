"""CRUD подписок: изоляция владельца + идемпотентность повторной подписки."""

SUBS = "/api/v1/subscriptions/"
FEED_A = "https://habr.com/ru/rss/hubs/python/articles/"
FEED_B = "https://habr.com/ru/rss/hubs/postgresql/articles/"


async def _subscribe(client, headers, feed_url=FEED_A):
    return await client.post(SUBS, json={"feed_url": feed_url}, headers=headers)


async def test_create_subscription(client, auth, user_a):
    r = await _subscribe(client, auth(user_a))
    assert r.status_code == 201
    assert r.json()["feed_url"] == FEED_A


async def test_list_returns_created(client, auth, user_a):
    await _subscribe(client, auth(user_a))
    r = await client.get(SUBS, headers=auth(user_a))
    assert r.status_code == 200
    assert [s["feed_url"] for s in r.json()] == [FEED_A]


async def test_duplicate_subscription_is_noop(client, auth, user_a):
    """Повторная подписка на ту же ленту не плодит дублей и не падает."""
    first = (await _subscribe(client, auth(user_a))).json()
    second = (await _subscribe(client, auth(user_a))).json()
    assert first["id"] == second["id"]

    r = await client.get(SUBS, headers=auth(user_a))
    assert len(r.json()) == 1


async def test_delete_subscription(client, auth, user_a):
    created = (await _subscribe(client, auth(user_a))).json()
    r = await client.delete(f"{SUBS}{created['id']}", headers=auth(user_a))
    assert r.status_code == 204

    r2 = await client.get(SUBS, headers=auth(user_a))
    assert r2.json() == []


async def test_delete_missing_returns_404(client, auth, user_a):
    import uuid

    r = await client.delete(f"{SUBS}{uuid.uuid4()}", headers=auth(user_a))
    assert r.status_code == 404


# ---------- изоляция владельца ----------


async def test_user_sees_only_own_subscriptions(client, auth, user_a, user_b):
    await _subscribe(client, auth(user_a), FEED_A)
    await _subscribe(client, auth(user_b), FEED_B)

    list_a = (await client.get(SUBS, headers=auth(user_a))).json()
    list_b = (await client.get(SUBS, headers=auth(user_b))).json()
    assert [s["feed_url"] for s in list_a] == [FEED_A]
    assert [s["feed_url"] for s in list_b] == [FEED_B]


async def test_cannot_delete_others_subscription(client, auth, user_a, user_b):
    created = (await _subscribe(client, auth(user_a))).json()
    r = await client.delete(f"{SUBS}{created['id']}", headers=auth(user_b))
    assert r.status_code == 404
    # подписка на месте у владельца
    assert (await client.get(SUBS, headers=auth(user_a))).json() != []
