from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Lease Deal Room"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5434/lease_deal_room"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "lease_chunks"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM / Embeddings
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    openai_api_key: str = ""

    # Storage & Concurrency
    storage_dir: Path = Path("../../storage")
    extraction_concurrency: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()