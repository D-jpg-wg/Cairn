#!/bin/sh
# Перед стартом приложения накатываем миграции на БД, затем запускаем uvicorn.
set -e

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
