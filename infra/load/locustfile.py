"""Нагрузочные сценарии Cairn (Locust, headless).

Нужен работающий compose-стек и access-токен load-юзера в окружении:

    export LOAD_ACCESS=$(infra/load/get_token.sh)

Каждый класс — отдельный профиль; выбирается позиционным аргументом:

    uvx locust -f infra/load/locustfile.py AuthMe      --headless -u 20 -r 10 -t 30s -H http://localhost:8000
    uvx locust -f infra/load/locustfile.py MainApi     --headless -u 20 -r 10 -t 30s -H http://localhost:8001
    uvx locust -f infra/load/locustfile.py UserJourney --headless -u 20 -r 10 -t 30s -H http://localhost:8001

Токен один на всех виртуальных юзеров: логин под лимитером 5/мин,
а /me и main-api от количества разных юзеров здесь не зависят.
"""

import os
import uuid

from locust import HttpUser, task

AUTH = "http://localhost:8000"
MAIN = "http://localhost:8001"
ENTRIES = "/api/v1/entries/"  # слэш обязателен: без него запрос уходит в StaticFiles


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['LOAD_ACCESS']}"}


class AuthMe(HttpUser):
    """auth в одиночку: GET /me = проверка RS256-подписи + чтение юзера из БД."""

    @task
    def me(self) -> None:
        self.client.get("/api/v1/auth/me", headers=bearer())


class MainApi(HttpUser):
    """main-api в одиночку: чтение и запись 3:1.

    POST — самый тяжёлый путь: INSERT + publish в Kafka + постановка Celery-задачи.
    Заметки (type=note), а не ссылки — чтобы enrich-воркер не ломился во внешний веб.
    """

    @task(3)
    def list_entries(self) -> None:
        self.client.get(ENTRIES, params={"limit": 20}, headers=bearer())

    @task(1)
    def create_note(self) -> None:
        self.client.post(
            ENTRIES,
            headers=bearer(),
            json={
                "title": f"load-{uuid.uuid4().hex[:8]}",
                "type": "note",
                "content": "нагрузочная заметка",
            },
        )


class UserJourney(HttpUser):
    """Сквозной профиль «живой пользователь»: auth + main-api + search разом.

    -H игнорируется — задачи ходят абсолютными URL в оба сервиса;
    name= схлопывает статистику по логическим операциям.
    """

    @task(2)
    def whoami(self) -> None:
        self.client.get(f"{AUTH}/api/v1/auth/me", headers=bearer(), name="auth GET /me")

    @task(4)
    def list_entries(self) -> None:
        self.client.get(
            f"{MAIN}{ENTRIES}",
            params={"limit": 20},
            headers=bearer(),
            name="main GET /entries/",
        )

    @task(1)
    def sql_search(self) -> None:
        self.client.get(
            f"{MAIN}{ENTRIES}",
            params={"q": "заметка", "limit": 20},
            headers=bearer(),
            name="main GET /entries/?q (SQL)",
        )

    @task(1)
    def grpc_search(self) -> None:
        self.client.get(
            f"{MAIN}/api/v1/entries/search",
            params={"q": "заметка"},
            headers=bearer(),
            name="main GET /entries/search (gRPC)",
        )

    @task(1)
    def create_note(self) -> None:
        self.client.post(
            f"{MAIN}{ENTRIES}",
            headers=bearer(),
            json={
                "title": f"load-{uuid.uuid4().hex[:8]}",
                "type": "note",
                "content": "нагрузочная заметка",
            },
            name="main POST /entries/",
        )
