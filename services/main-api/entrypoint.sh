#!/bin/sh
# Перед стартом приложения накатываем миграции на БД, затем запускаем uvicorn.
set -e

uv run alembic upgrade head

exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
