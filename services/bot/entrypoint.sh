#!/bin/sh
# Перед стартом бота накатываем миграции на bot-db, затем запускаем long-polling.
set -e

alembic upgrade head

exec python -m app.main
