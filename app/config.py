from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    environment: str = "development"

    # Database
    data_dir: Path = Path("data")
    sqlite_db_filename: str = "yad2_monitor.db"

    # Telegram
    telegram_bot_token: str
    telegram_bot_username: Optional[str] = None

    # Monitoring settings
    default_check_interval_minutes: int = 20
    min_check_interval_seconds: int = 300
    max_check_interval_seconds: int = 3600

    # Yad2
    yad2_base_domain: str = "www.yad2.co.il"

    def sqlite_db_path(self) -> Path:
        """Return absolute path to SQLite database file."""

        if not self.data_dir.is_absolute():
            base = Path.cwd()
            data_dir = base / self.data_dir
        else:
            data_dir = self.data_dir

        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / self.sqlite_db_filename


@lru_cache
def get_settings() -> Settings:
    return Settings()

