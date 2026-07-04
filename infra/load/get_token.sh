#!/usr/bin/env bash
# Печатает access-токен load-юзера (регистрирует его при первом запуске).
# Логин 1 раз за вызов — лимитер auth (5/мин) не мешает.
# ВАЖНО: юзер не привязан к Telegram — bot-notifier молча пропускает его события.
set -euo pipefail

AUTH="${AUTH:-http://localhost:8000}"
# .local/.test и т.п. EmailStr режет как special-use — нужен настоящий gTLD
EMAIL="loadtest@cairn.dev"
PASS="loadtest-password-1"

curl -s -o /dev/null -X POST "$AUTH/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" || true

# login кладёт access в cookie cairn_token — вынимаем его из Set-Cookie
curl -s -D - -o /dev/null -X POST "$AUTH/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | grep -io 'cairn_token=[^;]*' | head -1 | cut -d= -f2
