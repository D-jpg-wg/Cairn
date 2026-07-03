from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: str

    @property
    def db_url(self) -> str:
        """Async DSN для подключения к Postgres."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


setting = Settings()  # type: ignore[call-arg]  # значения берутся из env/.env в рантайме
