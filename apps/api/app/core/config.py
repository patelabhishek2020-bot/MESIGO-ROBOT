"""Runtime configuration — infrastructure only; owner secrets live in encrypted settings."""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("model_",),
    )

    app_name: str = "Mesigo AI"
    environment: str = Field(default="production", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug: bool = False

    database_url: str = Field(
        default="postgresql+asyncpg://mesigo:change-me@localhost:5432/mesigo",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql://mesigo:change-me@localhost:5432/mesigo",
        alias="DATABASE_URL_SYNC",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    secret_key: str = Field(default="dev-insecure-change-me", alias="SECRET_KEY")
    settings_encryption_key: str = Field(default="", alias="SETTINGS_ENCRYPTION_KEY")
    access_token_expire_minutes: int = 60 * 12
    algorithm: str = "HS256"

    api_cors_origins: str = Field(default="http://localhost:3000", alias="API_CORS_ORIGINS")

    bootstrap_owner_username: str = Field(default="owner", alias="BOOTSTRAP_OWNER_USERNAME")
    bootstrap_owner_password: str = Field(
        default="ChangeMeImmediately!", alias="BOOTSTRAP_OWNER_PASSWORD"
    )

    upload_dir: str = "/app/uploads"
    voice_sample_dir: str = "/app/voice_samples"

    @field_validator("database_url_sync", mode="before")
    @classmethod
    def normalize_sync_url(cls, v: str) -> str:
        if isinstance(v, str):
            return v.replace("postgresql+asyncpg://", "postgresql://")
        return v

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
