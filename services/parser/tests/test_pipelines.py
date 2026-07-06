"""KafkaPipeline: публикация item в page.parsed без реального брокера."""

from scrapy.settings import Settings

from app.items import PageItem
from app.pipelines import KafkaPipeline


class FakeProducer:
    def __init__(self, bootstrap_servers, value_serializer):
        self.bootstrap_servers = bootstrap_servers
        self.value_serializer = value_serializer
        self.started = False
        self.stopped = False
        self.sent: list[tuple[str, bytes]] = []

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def send_and_wait(self, topic, value):
        self.sent.append((topic, value))


class FakeSpider:
    def __init__(self):
        self.settings = Settings(
            {
                "PAGE_PARSED_TOPIC": "page.parsed",
                "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
            }
        )


async def test_pipeline_publishes_item_as_dict(monkeypatch):
    monkeypatch.setattr("app.pipelines.AIOKafkaProducer", FakeProducer)
    pipeline = KafkaPipeline()
    spider = FakeSpider()

    await pipeline.open_spider(spider)
    assert pipeline.producer.started
    assert pipeline.producer.bootstrap_servers == "kafka:9092"

    item = PageItem(url="https://habr.com/ru/articles/1/", title="Заголовок")
    result = await pipeline.process_item(item, spider)

    assert result is item
    assert len(pipeline.producer.sent) == 1
    topic, value = pipeline.producer.sent[0]
    assert topic == "page.parsed"
    assert value == dict(item)

    await pipeline.close_spider(spider)
    assert pipeline.producer.stopped


async def test_pipeline_value_serializer_encodes_unicode_json(monkeypatch):
    spider = FakeSpider()
    captured = {}

    class CapturingProducer(FakeProducer):
        def __init__(self, bootstrap_servers, value_serializer):
            captured["serializer"] = value_serializer
            super().__init__(bootstrap_servers, value_serializer)

    monkeypatch.setattr("app.pipelines.AIOKafkaProducer", CapturingProducer)
    pipeline = KafkaPipeline()
    await pipeline.open_spider(spider)

    encoded = captured["serializer"]({"title": "Заголовок"})

    # ensure_ascii=False — кириллица в Kafka читаемая, не \u-эскейпы.
    assert encoded == '{"title": "Заголовок"}'.encode("utf-8")
