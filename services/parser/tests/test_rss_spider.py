"""RssSpider: список лент из main-api, разбор RSS-айтема, вытяжка текста статьи."""

import json

import scrapy
from scrapy.settings import Settings
from twisted.python.failure import Failure

from app.items import PageItem
from app.spiders.rss import RssSpider
from tests.conftest import (
    FEED_URL,
    build_feed_response,
    build_html_response,
    build_json_response,
    build_node,
)

ITEM_XML = """<item>
<title><![CDATA[Заголовок статьи]]></title>
<link>https://habr.com/ru/articles/123/?utm_source=habrahabr&amp;utm_medium=rss</link>
<pubDate>Mon, 01 Jan 2024 10:00:00 +0300</pubDate>
<description><![CDATA[<p>Текст &amp; ещё текст</p>]]></description>
<category>Python</category>
<category>PostgreSQL</category>
</item>"""


def make_spider() -> RssSpider:
    spider = RssSpider()
    spider.settings = Settings({"MAIN_API_URL": "http://main-api:8000"})
    return spider


# ---------- start_requests / parse_feeds: лента приезжает из main-api ----------


async def test_start_requests_asks_main_api_for_feeds():
    spider = make_spider()
    requests = [r async for r in spider.start()]

    assert len(requests) == 1
    req = requests[0]
    assert req.url == "http://main-api:8000/api/v1/feeds"
    assert req.callback == spider.parse_feeds


def test_parse_feeds_yields_a_request_per_feed_url():
    spider = make_spider()
    urls = ["https://a.example/rss/", "https://b.example/rss/"]
    response = build_json_response(
        "http://main-api:8000/api/v1/feeds", json.dumps(urls)
    )

    requests = list(spider.parse_feeds(response))

    assert [r.url for r in requests] == urls
    # Без явного callback — Scrapy сам роутит на spider._parse (родной
    # диспетчер XMLFeedSpider); публичного parse в этой версии нет.
    assert all(r.callback is None for r in requests)


def test_parse_feeds_empty_list_yields_nothing():
    spider = make_spider()
    response = build_json_response("http://main-api:8000/api/v1/feeds", "[]")

    assert list(spider.parse_feeds(response)) == []


def test_on_feeds_failed_does_not_raise():
    spider = make_spider()
    try:
        raise ConnectionError("main-api unreachable")
    except ConnectionError:
        failure = Failure()

    spider.on_feeds_failed(failure)  # просто не должно упасть


# ---------- parse_node: RSS item -> Request(parse_article) с заполненным item ----------


def test_parse_node_builds_request_with_cleaned_url_and_fields():
    spider = make_spider()
    response = build_feed_response()
    node = build_node(ITEM_XML)

    requests = list(spider.parse_node(response, node))

    assert len(requests) == 1
    req = requests[0]
    # utm-хвост срезан url_query_cleaner-ом — иначе один и тот же материал
    # с разными utm посчитался бы разными записями (ключ идемпотентности — url).
    assert req.url == "https://habr.com/ru/articles/123/"
    assert req.callback == spider.parse_article
    assert req.errback == spider.on_article_failed
    assert req.dont_filter is True

    item = req.cb_kwargs["item"]
    assert item["source_url"] == FEED_URL
    assert item["url"] == "https://habr.com/ru/articles/123/"
    assert item["title"] == "Заголовок статьи"
    assert item["tags"] == ["Python", "PostgreSQL"]
    assert item["published_at"] == "2024-01-01T10:00:00+03:00"


def test_parse_node_summary_strips_tags_and_decodes_entities():
    spider = make_spider()
    node = build_node(ITEM_XML)

    item = list(spider.parse_node(build_feed_response(), node))[0].cb_kwargs["item"]

    # Порядок важен: сущности раскодированы ПОСЛЕ среза тегов, иначе
    # &lt;script&gt; тегом бы не считался и попал бы в summary как текст.
    assert item["summary"] == "Текст & ещё текст"


def test_parse_node_missing_pub_date_is_none():
    spider = make_spider()
    xml = ITEM_XML.replace("<pubDate>Mon, 01 Jan 2024 10:00:00 +0300</pubDate>", "")
    node = build_node(xml)

    item = list(spider.parse_node(build_feed_response(), node))[0].cb_kwargs["item"]

    assert item["published_at"] is None


# ---------- parse_article: тело статьи ----------


ARTICLE_HTML = """
<html><body>
<div id="post-content-body">
<p>Первый абзац.</p>
<h2>Заголовок раздела</h2>
<p>Второй   абзац с   лишними пробелами.</p>
<ul><li>Пункт один</li><li>Пункт два</li></ul>
<script>console.log('shouldnt appear')</script>
</div>
</body></html>
"""


def test_parse_article_joins_body_blocks():
    spider = make_spider()
    item = PageItem(url="https://habr.com/ru/articles/123/")
    response = build_html_response("https://habr.com/ru/articles/123/", ARTICLE_HTML)

    result = list(spider.parse_article(response, item))

    assert len(result) == 1
    content = result[0]["content"]
    assert content == (
        "Первый абзац.\n\n"
        "Заголовок раздела\n\n"
        "Второй абзац с лишними пробелами.\n\n"
        "Пункт один\n\n"
        "Пункт два"
    )


def test_parse_article_empty_body_sets_content_none():
    spider = make_spider()
    item = PageItem(url="https://habr.com/ru/articles/404/")
    response = build_html_response(
        "https://habr.com/ru/articles/404/",
        "<html><body>нет такого блока</body></html>",
    )

    result = list(spider.parse_article(response, item))

    assert result[0]["content"] is None


# ---------- on_article_failed: 403/таймаут -> событие уходит с тизером ----------


def test_on_article_failed_yields_the_teaser_item():
    spider = make_spider()
    item = PageItem(
        url="https://habr.com/ru/articles/403/", title="Заголовок", summary="тизер"
    )
    request = scrapy.Request(
        "https://habr.com/ru/articles/403/", cb_kwargs={"item": item}
    )
    try:
        raise ConnectionError("403 Forbidden")
    except ConnectionError:
        failure = Failure()
    failure.request = request

    result = list(spider.on_article_failed(failure))

    assert result == [item]
