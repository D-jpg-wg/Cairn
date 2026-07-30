import json
import scrapy
from email.utils import parsedate_to_datetime
from w3lib.url import url_query_cleaner
from w3lib.html import remove_tags, replace_escape_chars, replace_entities
from scrapy.spiders import XMLFeedSpider

from app.items import PageItem


class RssSpider(XMLFeedSpider):
    name = "rss"
    iterator = "iternodes"
    itertag = "item"

    async def start(self):
        """Список лент — не в коде, а у main-api: чей-то /feeds решает подписка,
        не паук (парсер про юзеров не знает, database-per-service).

        Scrapy >=2.13 зовёт именно start() (async-генератор), не start_requests() —
        старый синхронный метод в этой версии библиотеки вообще не вызывается."""
        main_api_url = self.settings["MAIN_API_URL"]
        yield scrapy.Request(
            f"{main_api_url}/api/v1/feeds",
            callback=self.parse_feeds,
            errback=self.on_feeds_failed,
            meta={"dont_cache": True},
        )

    def parse_feeds(self, response):
        for feed_url in json.loads(response.text):
            # Без callback: Scrapy сам роутит на spider._parse — родной диспетчер
            # XMLFeedSpider (итерация нод -> parse_node). Публичного alias'а
            # parse у XMLFeedSpider в этой версии Scrapy больше нет.
            yield scrapy.Request(feed_url, dont_filter=True, meta={"dont_cache": True})

    def on_feeds_failed(self, failure):
        """main-api недоступен — прогон пустой, а не падает целиком."""
        self.logger.error("Не удалось получить список лент: %r", failure.value)

    def parse_node(self, response, node):
        pub = node.xpath("pubDate/text()").get()
        raw = node.xpath("description/text()").get() or ""
        summary = replace_escape_chars(
            replace_entities(remove_tags(raw)),
            which_ones=("\n", "\t", "\r"),
            replace_by=" ",
        ).strip()
        item = PageItem(
            source_url=response.url,
            url=url_query_cleaner(node.xpath("link/text()").get(), ()),
            title=node.xpath("title/text()").get(),
            summary=summary or None,
            published_at=parsedate_to_datetime(pub).isoformat() if pub else None,
            tags=node.xpath("category/text()").getall()[:5],
        )

        yield scrapy.Request(
            item["url"],
            callback=self.parse_article,
            errback=self.on_article_failed,
            cb_kwargs={"item": item},
            dont_filter=True,
        )

    def parse_article(self, response, item):
        parts = []
        for block in response.css("#post-content-body").css("p, h2, h3, h4, li, pre"):
            text = " ".join(" ".join(block.css("::text").getall()).split())
            if text:
                parts.append(text)
        item["content"] = "\n\n".join(parts) or None
        yield item

    def on_article_failed(self, failure):
        """Страница не отдалась (403, таймаут) — событие уходит хотя бы с тизером."""
        yield failure.request.cb_kwargs["item"]
