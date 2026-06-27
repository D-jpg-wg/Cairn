from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str

    # Окружение: "dev" | "prod". Влияет на флаг Secure у cookie:
    # по http://localhost браузер Secure-cookie не сохранит.
    environment: str = "dev"

    # Куда вернуть пользователя после успешного входа (фронт main-app).
    app_url: str = "http://localhost:8001/"

    db_name: str
    db_user: str
    db_password: str
    db_host: str
    db_port: str

    # Пути к RSA-ключам для подписи JWT (RS256).
    # Приватный — только у auth-сервиса; публичный раздаётся потребителям токенов.
    jwt_private_key_path: Path = Path("keys/jwt_private.pem")
    jwt_public_key_path: Path = Path("keys/jwt_public.pem")

    # OAuth 2.0
    google_client_id: str
    google_client_secret: str
    google_redirect_url: str

    # Секрет для подписи cookie-сессии (хранит OAuth state).
    session_secret: str

    @property
    def cookie_secure(self) -> bool:
        """Secure-cookie только в проде (по http://localhost она не сохранится)."""
        return self.environment == "prod"

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def jwt_private_key(self) -> str:
        return self.jwt_private_key_path.read_text()

    @property
    def jwt_public_key(self) -> str:
        return self.jwt_public_key_path.read_text()


setting = Setting()  # type: ignore[call-arg]  # значения берутся из env/.env в рантайме
