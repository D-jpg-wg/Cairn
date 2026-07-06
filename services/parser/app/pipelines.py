# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import json

from aiokafka import AIOKafkaProducer


class KafkaPipeline:
    """Публикует каждый item событием page.parsed."""

    async def open_spider(self, spider):
        self.topic = spider.settings["PAGE_PARSED_TOPIC"]
        self.producer = AIOKafkaProducer(
            bootstrap_servers=spider.settings["KAFKA_BOOTSTRAP_SERVERS"],
            value_serializer=lambda x: json.dumps(x, ensure_ascii=False).encode(),
        )
        await self.producer.start()

    async def close_spider(self, spider):
        await self.producer.stop()

    async def process_item(self, item, spider):
        await self.producer.send_and_wait(self.topic, dict(item))
        return item
