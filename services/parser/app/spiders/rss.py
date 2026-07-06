from email.utils import parsedate_to_datetime
from w3lib.url import url_query_cleaner
from scrapy.spiders import XMLFeedSpider

from app.items import PageItem


class RssSpider(XMLFeedSpider):
    name = "rss"
    start_urls = ["https://habr.com/ru/rss/articles/"]
    iterator = "iternodes"
    itertag = "item"

    def parse_node(self, response, node):
        pub = node.xpath("pubDate/text()").get()
        yield PageItem(
            source_url=response.url,
            url=url_query_cleaner(node.xpath("link/text()").get(), ()),
            title=node.xpath("title/text()").get(),
            summary=node.xpath("description/text()").get(),
            published_at=parsedate_to_datetime(pub).isoformat() if pub else None,
        )
