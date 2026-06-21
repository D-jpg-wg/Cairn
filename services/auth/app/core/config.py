from pydantic_settings import BaseSettings, SettingsConfigDict


class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str

    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: str

    secret_key: str

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


setting = Setting()  # type: ignore[call-arg]  # значения берутся из env/.env в рантайме
