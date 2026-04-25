from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    APP_NAME: str = "SintezCar Backend"
    DEBUG: bool = False
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/sintezcar"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "super-secret-change-me"
    TELEGRAM_BOT_TOKEN: str = ""  # ← Теперь UPPER_CASE, как в .env
    GOOGLE_CREDENTIALS_PATH: str = "google_credentials.json"
    YANDEX_OAUTH_TOKEN: str = ""
    YANDEX_CALENDAR_ID: str = "default"
    YANDEX_LOGIN: str = ""              # makcsoop@yandex.ru
    YANDEX_APP_PASSWORD: str = ""       # пароль приложения из Яндекс.Паспорта

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # Позволяет обращаться и к telegram_bot_token, и к TELEGRAM_BOT_TOKEN
        extra="ignore"
    )

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

settings = Settings()