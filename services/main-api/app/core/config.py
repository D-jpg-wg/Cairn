from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str

    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: str

    celery_broker_url: str = "redis://localhost:6379/0"

    kafka_bootstrap_servers: str = "localhost:9092"

    # main-api только ПРОВЕРЯЕТ JWT — нужен лишь публичный ключ auth-сервиса.
    jwt_public_key_path: Path = Path("keys/jwt_public.pem")

    @property
    def db_url(self) -> str:
        """Async DSN для подключения к Postgres."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def sync_db_url(self) -> str:
        return self.db_url.replace("+asyncpg", "+psycopg2")

    @property
    def jwt_public_key(self) -> str:
        """Публичный RSA-ключ auth-сервиса для проверки JWT."""
        return self.jwt_public_key_path.read_text()


setting = Setting()  # type: ignore[call-arg]  # значения берутся из env/.env в рантайме
