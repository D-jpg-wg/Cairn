# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class PageItem(scrapy.Item):
    """Одна страница из ленты — будущий payload события page.parsed."""

    source_url = scrapy.Field()
    url = scrapy.Field()
    title = scrapy.Field()
    summary = scrapy.Field()
    published_at = scrapy.Field()
