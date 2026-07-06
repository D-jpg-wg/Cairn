"""GET /feeds — публичный список лент для парсера, без авторизации."""

FEEDS = "/api/v1/feeds"
SUBS = "/api/v1/subscriptions/"
FEED_A = "https://habr.com/ru/rss/hubs/python/articles/"
FEED_B = "https://habr.com/ru/rss/hubs/postgresql/articles/"


async def test_feeds_empty_by_default(client):
    r = await client.get(FEEDS)
    assert r.status_code == 200
    assert r.json() == []


async def test_feeds_requires_no_auth(client, auth, user_a):
    """Парсер не носит JWT — эндпоинт обязан отвечать без Authorization."""
    await client.post(SUBS, json={"feed_url": FEED_A}, headers=auth(user_a))
    r = await client.get(FEEDS)  # без headers
    assert r.status_code == 200
    assert r.json() == [FEED_A]


async def test_feeds_are_deduplicated_across_users(client, auth, user_a, user_b):
    """Двое подписаны на одну ленту — в списке она один раз (парсер не дублирует crawl)."""
    await client.post(SUBS, json={"feed_url": FEED_A}, headers=auth(user_a))
    await client.post(SUBS, json={"feed_url": FEED_A}, headers=auth(user_b))
    await client.post(SUBS, json={"feed_url": FEED_B}, headers=auth(user_b))

    r = await client.get(FEEDS)
    assert sorted(r.json()) == sorted([FEED_A, FEED_B])
