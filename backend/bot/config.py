# bot/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class BotSettings(BaseSettings):
    # Обязательные поля для бота
    BOT_TOKEN: str
    DATABASE_URL: str
    
    # Опциональные поля
    ADMIN_IDS: str = ""  # Telegram ID через запятую
    LOG_LEVEL: str = "INFO"

    @property
    def admin_ids_list(self) -> List[int]:
        """Возвращает список ID админов как list[int]"""
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]

    # 👇 КЛЮЧЕВОЕ: разрешаем лишние переменные из .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",  # 👈 Игнорировать переменные, которые не описаны в классе
        case_sensitive=False
    )

settings = BotSettings()