import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    demo_mode: bool = True
    gemini_api_key: str = ""
    openai_api_key: str = ""
    database_url: str = "sqlite:///./recoveriq.db"
    high_value_threshold: float = 25000.0
    max_retries: int = 3
    min_retry_delay_hours: int = 6
    max_reminder_per_24h: int = 1
    low_confidence_threshold: float = 0.6

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Auto-detect live mode
if settings.gemini_api_key or settings.openai_api_key:
    settings.demo_mode = False
