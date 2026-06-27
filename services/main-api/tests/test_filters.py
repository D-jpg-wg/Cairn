"""Фильтр по тегам (OR — объединение) и поиск по тексту."""

ENTRIES = "/api/v1/entries/"
TAGS = "/api/v1/entries/tags"


async def _create(client, headers, title, tags, content="тело"):
    return await client.post(
        ENTRIES,
        json={"title": title, "type": "note", "content": content, "tags": tags},
        headers=headers,
    )


async def _titles(client, headers, params):
    r = await client.get(ENTRIES, headers=headers, params=params)
    assert r.status_code == 200
    return sorted(e["title"] for e in r.json())


async def test_filter_single_tag(client, auth, user_a):
    h = auth(user_a)
    await _create(client, h, "Py", ["python"])
    await _create(client, h, "Kafka", ["kafka"])
    assert await _titles(client, h, {"tag": "python"}) == ["Py"]


async def test_filter_multiple_tags_is_union(client, auth, user_a):
    h = auth(user_a)
    await _create(client, h, "Py", ["python"])
    await _create(client, h, "Kafka", ["kafka"])
    await _create(client, h, "Other", ["misc"])
    # OR: запись с любым из выбранных тегов
    assert await _titles(client, h, [("tag", "python"), ("tag", "kafka")]) == [
        "Kafka",
        "Py",
    ]


async def test_search_matches_title_and_content(client, auth, user_a):
    h = auth(user_a)
    await _create(client, h, "Про JWT", ["security"], content="о токенах")
    await _create(client, h, "Заметка", ["misc"], content="внутри слово jwt тоже")
    await _create(client, h, "Лишняя", ["misc"], content="ничего")
    assert await _titles(client, h, {"q": "jwt"}) == ["Заметка", "Про JWT"]


async def test_tag_and_search_combined(client, auth, user_a):
    h = auth(user_a)
    await _create(client, h, "Py-JWT", ["python"], content="jwt")
    await _create(client, h, "Py-other", ["python"], content="ничего")
    await _create(client, h, "Kafka-JWT", ["kafka"], content="jwt")
    # python AND содержит jwt
    assert await _titles(client, h, {"tag": "python", "q": "jwt"}) == ["Py-JWT"]


async def test_tags_endpoint_returns_own_tags(client, auth, user_a, user_b):
    await _create(client, auth(user_a), "A", ["python", "idea"])
    await _create(client, auth(user_b), "B", ["kafka"])
    r = await client.get(TAGS, headers=auth(user_a))
    assert r.status_code == 200
    assert sorted(t["name"] for t in r.json()) == ["idea", "python"]
