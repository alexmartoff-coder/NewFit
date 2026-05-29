# settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/newfit"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
