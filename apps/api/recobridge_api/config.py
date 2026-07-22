from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RECOBRIDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_token: str = Field(default="recobridge-demo-token", min_length=8)
    database_url: str = "memory://"
    model_bundle_path: str | None = None
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
