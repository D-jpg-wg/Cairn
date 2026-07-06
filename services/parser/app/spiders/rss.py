import scrapy
from email.utils import parsedate_to_datetime
from w3lib.url import url_query_cleaner
from w3lib.html import remove_tags, replace_escape_chars, replace_entities
from scrapy.spiders import XMLFeedSpider

from app.items import PageItem


class RssSpider(XMLFeedSpider):
    name = "rss"
    # TODO: список лент должен приезжать из подписок (main-api), а не из кода —
    # решить на шаге расписания, вместе с тем, кто вообще запускает прогоны.
    start_urls = [
        "https://habr.com/ru/rss/hubs/python/articles/",
        "https://habr.com/ru/rss/hubs/postgresql/articles/",
    ]
    iterator = "iternodes"
    itertag = "item"

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
