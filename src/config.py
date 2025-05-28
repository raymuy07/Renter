from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://localhost/blog_scraper"
    redis_url: str = "redis://localhost:6379/0"
    
    # API Keys
    openai_api_key: str = ""
    
    # App
    secret_key: str = "your-secret-key"
    debug: bool = True
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
