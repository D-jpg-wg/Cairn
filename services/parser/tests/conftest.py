"""Общие фикстуры тестов парсера.

Паук гоняется без сети: узлы/ответы собираем сами через Selector/TextResponse,
не поднимая реальный Scrapy Crawler — parse_node/parse_article/parse_feeds это
обычные методы, им достаточно (response, node) с нужной формой.
"""

from scrapy.http import HtmlResponse, TextResponse
from scrapy.selector import Selector

FEED_URL = "https://habr.com/ru/rss/hubs/python/articles/"


def build_node(item_xml: str):
    """<item>...</item> одной ленты -> Selector, каким его видит parse_node."""
    sel = Selector(text=item_xml, type="xml")
    return sel.xpath("//item")[0]


def build_feed_response(url: str = FEED_URL) -> TextResponse:
    return TextResponse(url=url, body=b"", encoding="utf-8")


def build_html_response(url: str, html: str) -> HtmlResponse:
    return HtmlResponse(url=url, body=html.encode("utf-8"), encoding="utf-8")


def build_json_response(url: str, body: str) -> TextResponse:
    return TextResponse(url=url, body=body.encode("utf-8"), encoding="utf-8")
