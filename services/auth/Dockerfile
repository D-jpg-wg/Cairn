FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /code

RUN pip install uv --no-cache-dir

# Зависимости ставим отдельным слоем — кэшируется, пока не менялись pyproject/uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# Запускаемся из-под непривилегированного пользователя.
RUN chmod +x entrypoint.sh \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /code
USER appuser

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
