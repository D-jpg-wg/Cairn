from email.utils import parsedate_to_datetime
from w3lib.url import url_query_cleaner
from w3lib.html import remove_tags, replace_escape_chars, replace_entities
from scrapy.spiders import XMLFeedSpider

from app.items import PageItem


class RssSpider(XMLFeedSpider):
    name = "rss"
    start_urls = ["https://habr.com/ru/rss/articles/"]
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
        yield PageItem(
            source_url=response.url,
            url=url_query_cleaner(node.xpath("link/text()").get(), ()),
            title=node.xpath("title/text()").get(),
            summary=summary or None,
            published_at=parsedate_to_datetime(pub).isoformat() if pub else None,
            tags=node.xpath("category/text()").getall()[:5],
        )
