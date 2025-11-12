from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict
import os
import json
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
    quiet_hours_start: int = 23  # 23:00 (11 PM)
    quiet_hours_end: int = 8     # 08:00 (8 AM)

    # Yad2
    yad2_base_domain: str = "www.yad2.co.il"

    # Authentication - supports both single and multiple credentials
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    auth_credentials: Optional[str] = None  # JSON string: [{"username":"user1","password":"pass1"},...]
    
    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours (no notifications)."""
        from datetime import datetime
        current_hour = datetime.now().hour
        
        # Handle cases where quiet hours span midnight
        if self.quiet_hours_start > self.quiet_hours_end:
            # e.g., 23:00 to 08:00 (spans midnight)
            return current_hour >= self.quiet_hours_start or current_hour < self.quiet_hours_end
        else:
            # e.g., 22:00 to 06:00 (doesn't span midnight, same day)
            return self.quiet_hours_start <= current_hour < self.quiet_hours_end
    
    def get_valid_credentials(self) -> List[Dict[str, str]]:
        """Return list of valid username/password pairs."""
        credentials = []
        
        # Try to load from JSON format first
        if self.auth_credentials:
            try:
                creds_list = json.loads(self.auth_credentials)
                if isinstance(creds_list, list):
                    credentials.extend(creds_list)
            except json.JSONDecodeError:
                # If JSON fails, try simple format: user1:pass1,user2:pass2
                for pair in self.auth_credentials.split(','):
                    pair = pair.strip()
                    if ':' in pair:
                        username, password = pair.split(':', 1)
                        credentials.append({"username": username.strip(), "password": password.strip()})
        
        # Add single credential if provided
        if self.auth_username and self.auth_password:
            credentials.append({"username": self.auth_username, "password": self.auth_password})
        
        return credentials
    
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

