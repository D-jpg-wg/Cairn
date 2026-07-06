#!/bin/sh
# Twisted reactor нельзя стартовать дважды в одном процессе — поэтому расписание
# это цикл свежих процессов `scrapy crawl`, а не что-то внутри самого паука.
set -e

INTERVAL="${CRAWL_INTERVAL:-3600}"

while true; do
    scrapy crawl rss
    echo "Прогон завершён, следующий через ${INTERVAL}с" >&2
    sleep "$INTERVAL"
done
