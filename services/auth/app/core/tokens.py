"""Единый источник правды по токенам и cookie сессии.

Сроки жизни нужны сразу в трёх местах (exp у JWT, expires_at записи refresh в БД
и max_age у cookie) — держим их здесь, чтобы не расходились копии.
"""

from datetime import timedelta

# Время жизни токенов.
ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)

# Имена и путь cookie сессии.
ACCESS_COOKIE = "cairn_token"
REFRESH_COOKIE = "cairn_refresh"
REFRESH_PATH = "/api/v1/auth"  # refresh-cookie отправляется только на auth-роуты

# Ключ OAuth state в сессии (CSRF между /oauth/google и /callback).
OAUTH_STATE_KEY = "oauth_state"
