# Cairn

[![CI](https://github.com/D-jpg-wg/Cairn/actions/workflows/ci.yml/badge.svg)](https://github.com/D-jpg-wg/Cairn/actions/workflows/ci.yml)
[![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Go 1.26](https://img.shields.io/badge/Go-1.26-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Apache Kafka](https://img.shields.io/badge/Apache%20Kafka-231F20?logo=apachekafka&logoColor=white)](https://kafka.apache.org/)
[![Redis](https://img.shields.io/badge/Redis-FF4438?logo=redis&logoColor=white)](https://redis.io/)
[![gRPC](https://img.shields.io/badge/gRPC-244c5a?logo=grpc&logoColor=white)](https://grpc.io/)
[![Docker](https://img.shields.io/badge/Docker%20Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)

Личная база знаний — сервис, куда стекаются заметки, ссылки, код-сниппеты и
спарсенные статьи (веб, Telegram-бот, парсер), а затем находятся обратно: по
тегу, по тексту или по смыслу (семантический поиск на дальних фазах).

Практическая цель проекта — не продукт, а **полигон**: каждый сервис добавляет
повод пощупать конкретную технологию вживую (Auth — JWT и database-per-service,
Kafka — события между сервисами, gRPC — типизированные синхронные вызовы,
Celery — фон внутри сервиса, observability — как выглядит «сломалось» в системе
из пяти сервисов).

Полная архитектура, схемы путей передачи и дорожная карта по фазам 0–8 —
в [`roadmap.html`](./roadmap.html) (открыть в браузере).

## Дорожная карта — текущий статус

| Фаза | Что | Статус |
|------|-----|--------|
| 00 | Подготовка: монорепо, окружение, pre-commit | ✅ готово |
| 01 | Скелет: `auth` (JWT) + `main-api`, database-per-service | ✅ готово |
| 02 | Асинхронность: Celery + Redis, Kafka, первый gRPC-вызов | ✅ готово |
| 03 | Бот: Aiogram-сервис, REST к Main API + consumer Kafka | 🔜 следующая |
| 04 | Парсинг: Scrapy по расписанию → Kafka | ⬜ |
| 05 | Наблюдаемость: логи, health-checks, Prometheus + Grafana | ⬜ |
| 06 | CI/CD: сборка образов, push в registry | 🟡 частично (lint+test на PR) |
| 07 | Kubernetes: Helm, Ingress | ⬜ |
| 08 | ML-сервис: инференс embeddings | ⬜ |

## Архитектура

Три разных пути для трёх разных задач — внешний трафик (REST), внутренние
синхронные вызовы (gRPC) и события (Kafka):

```
                    ┌──────────────┐
   клиенты ──REST──▶│   main-api   │──gRPC──▶  search   (топ похожих заметок)
   (web, bot)       │   FastAPI    │
                    │   ядро       │──events─▶  Kafka  ──▶ bot / parser
                    └──────┬───────┘
                           │ проверяет JWT (public key)
                    ┌──────▼───────┐         ┌──────────────────────┐
                    │     auth     │         │ Celery worker + beat  │
                    │  JWT / OAuth │         │ фон внутри main-api   │
                    └──────────────┘         └──────────┬───────────┘
                       │                                 │
                  auth-db (PG)   main-db (PG)         redis (брокер)
```

- **`auth`** выдаёт и подписывает JWT (приватным ключом). **`main-api`** только
  *проверяет* токены публичным ключом — приватного ключа у него нет.
- **database-per-service**: у `auth` и `main-api` свои Postgres-инстансы, никто
  не лезет в чужую схему — только через сеть (REST / gRPC / Kafka).
- **`search`** — пока gRPC-заглушка (контракт из `proto/`, реальной логики
  поиска ещё нет); это полигон для кодогенерации, deadline, grpcurl.

## Что такое монорепо здесь

Один git-репозиторий, внутри — **несколько самостоятельных сервисов**. Это не
«один большой проект», а несколько отдельных проектов, которые лежат рядом и
версионируются вместе. Сервисы максимально независимы: у каждого свои
зависимости, своя БД, свой Docker-образ, свой деплой. Общий — только git, плюс
несколько сквозных вещей (контракты, инфра, линтер, CI).

```
Cairn/
├── services/
│   ├── auth/         JWT, OAuth2 · своя БД (FastAPI)        ✅
│   ├── main-api/     ядро, бизнес-логика, Celery, Kafka     ✅
│   ├── search/       gRPC-сервис (заглушка под embeddings)  ✅
│   ├── bot/          Telegram-бот (Aiogram)                 🔜 скелет
│   └── parser/       парсинг по расписанию (Scrapy)         ⬜ скелет
│       ├── pyproject.toml   зависимости ТОЛЬКО этого сервиса
│       ├── app/             код
│       ├── alembic/         миграции его БД (где нужна)
│       ├── tests/
│       └── Dockerfile       как собрать его в образ
│
├── proto/                 ОБЩЕЕ: gRPC-контракты между сервисами (buf)
├── infra/                 ОБЩЕЕ: инфраструктурные конфиги
├── docker-compose.yml     ОБЩЕЕ: поднять весь стек локально разом
├── .pre-commit-config.yaml ОБЩЕЕ: линтер/форматтер ruff на весь репо
└── .github/workflows/     ОБЩЕЕ: CI на каждый PR
```

## Два уровня работы

В любой момент ты находишься на одном из двух уровней:

1. **Уровень сервиса** (90% времени) — внутри `services/<name>/`. Как обычный
   отдельный проект: пишешь код, добавляешь зависимости, гоняешь тесты.
   Зависимости одного сервиса не видят зависимостей другого — это специально.
2. **Уровень репозитория** (корень) — общие вещи, касающиеся всех:
   `docker compose up`, контракты в `proto/`, pre-commit и CI.

Граница между уровнями — и есть «микросервисность». Сервис общается с другим
**не импортом Python-кода**, а через сеть: REST, gRPC (контракт в `proto/`) или
события Kafka. Никаких `from main_api.app import ...` внутри `auth`.

## Инструменты

- **Python 3.14**, менеджер пакетов/окружений — **[uv](https://docs.astral.sh/uv/)**.
- venv'ом не управляют вручную (`source activate` не нужен): `uv run` сам
  активирует нужное окружение на время команды. У каждого сервиса свой `.venv`
  рядом с его `pyproject.toml`.
- Линтер/форматтер — **ruff** через pre-commit.

## Быстрый старт — весь стек локально

```bash
# из корня репозитория
docker compose up --build      # все сервисы + postgres / kafka / redis разом
```

Образы запекают код внутрь — после правок нужен `--build`, иначе в контейнере
останется старая версия.

После старта поднимаются:

| Сервис | Адрес | Назначение |
|--------|-------|------------|
| `auth` | http://localhost:8000 | регистрация/логин, JWT |
| `main-api` | http://localhost:8001 | ядро, бизнес-логика (Swagger на `/docs`) |
| `search` | `localhost:50051` | gRPC-сервис (заглушка) |
| `kafka-ui` | http://localhost:8080 | веб-просмотр топиков Kafka |
| `auth-db` | `localhost:5432` | Postgres сервиса auth |
| `main-db` | `localhost:5433` | Postgres сервиса main-api |
| `redis` | `localhost:6379` | брокер Celery + кэш |
| `kafka` | `localhost:9092` | шина событий |

Рядом с `main-api` поднимаются `main-api-worker` (Celery worker) и
`main-api-beat` (Celery beat) из того же образа.

## Работа над одним сервисом

```bash
cd services/auth                       # спускаешься на уровень сервиса
uv sync                                # создаёт ./.venv и ставит зависимости auth
uv run uvicorn app.main:app --reload   # запуск сервиса
uv run pytest                          # тесты только этого сервиса
uv add "fastapi[standard]"             # добавить зависимость → в его pyproject.toml
```

Переключаешься на другой сервис — просто `cd` в его папку, `uv run` подхватит
уже его окружение.

## Контракты gRPC — `proto/`

В `proto/` лежат `.proto`-контракты на вызовы между сервисами (сборка через
**buf**). Из них кодогенерацией получаются Python-классы для обеих сторон
вызова; сгенерированный код кладётся в `services/*/app/grpc_gen/`. Номера полей
в `.proto` — это контракт на проводе: новые поля добавлять можно, переиспользовать
или удалять старый номер — нельзя. На каждый gRPC-вызов ставится deadline,
обработчики идемпотентны (ретраи могут прислать вызов дважды).

## Pre-commit

Хуки гигиены и ruff ставятся отдельно от окружений сервисов:

```bash
uvx pre-commit install        # один раз — поставить git-хук
uvx pre-commit run --all-files
```

## CI

`.github/workflows/ci.yml` на каждый PR гоняет `ruff check` по всему репо и
тесты — но **только для изменённых сервисов** (path-filters через
`dorny/paths-filter`), чтобы не пересобирать всё подряд. Для `auth` в CI
генерируются временные JWT-ключи.

## Лицензия

[MIT](./LICENSE).
