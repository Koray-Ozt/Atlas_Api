"""Runtime configuration, read from ATLAS_* environment variables or a local .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATLAS_", env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "atlas"
    mongo_timeout_ms: int = 5000
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
