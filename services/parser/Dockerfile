# ---------- builder: тут живут uv, кэши и сборка venv ----------
FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /code

# Слой зависимостей кэшируется отдельно от кода.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ---------- runtime: чистый образ, только venv + код ----------
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 1000 appuser

WORKDIR /code

COPY --from=builder --chown=appuser:appuser /code/.venv /code/.venv
COPY --chown=appuser:appuser . .

# venv в PATH → scrapy берётся из него без uv.
ENV PATH="/code/.venv/bin:$PATH"

RUN chmod +x entrypoint.sh
USER appuser

# Порт не EXPOSE-им: парсер ничего не слушает, только ходит наружу.
ENTRYPOINT ["./entrypoint.sh"]
