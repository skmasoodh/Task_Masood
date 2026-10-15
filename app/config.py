"""Application configuration loaded from environment variables / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "attendance_db"

    # Business rules
    work_start_hour: int = 9
    work_start_minute: int = 0
    standard_work_minutes: int = 480
    late_grace_minutes: int = 10
    timezone: str = "UTC"


settings = Settings()
