from pydantic_settings import BaseSettings
from typing import List

class BotSettings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    ADMIN_IDS: str = ""  # Telegram ID через запятую
    LOG_LEVEL: str = "INFO"

    @property
    def admin_ids_list(self) -> List[int]:
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = BotSettings()