# settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

import os

class Settings(BaseSettings):
    BOT_TOKEN: str = "mock_token"
    # Remove default localhost URL to avoid confusion.
    # Use SQLite as a fallback or require DATABASE_URL.
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Railway-specific environment variable handling
        env_db_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")
        if env_db_url:
            self.DATABASE_URL = env_db_url

        # Handle Postgres driver prefix for asyncpg
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        elif self.DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in self.DATABASE_URL:
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Log (obfuscated) URL for debugging
        db_log = self.DATABASE_URL.split('@')[-1] if '@' in self.DATABASE_URL else self.DATABASE_URL
        print(f"INFO: Database URL configured to: {db_log}")

    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None
    ADMIN_IDS: str = ""

    YOOKASSA_SHOP_ID: Optional[str] = None
    YOOKASSA_SECRET_KEY: Optional[str] = None
    YOOKASSA_TEST_MODE: bool = True
    YOOKASSA_PROVIDER_TOKEN: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix=""
    )

settings = Settings()
