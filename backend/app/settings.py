from functools import lru_cache

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    base_url: AnyUrl = Field(default="https://lab.aismallbizguru.com", alias="BASE_URL")
    sqlite_path: str = Field(default="../data/sqlite/labbox.db", alias="SQLITE_PATH")
    app_config_path: str = Field(default="../config/apps.yaml", alias="APP_CONFIG_PATH")
    cors_allow_origins: str = Field(default="", alias="CORS_ALLOW_ORIGINS")
    version: str = "0.2.1"

    admin_password_hash: str | None = Field(default=None, alias="ADMIN_PASSWORD_HASH")
    admin_session_secret: str | None = Field(default=None, alias="ADMIN_SESSION_SECRET")
    api_token_pepper: str | None = Field(default=None, alias="API_TOKEN_PEPPER")

    minio_endpoint: str = Field(default="localhost:9000", alias="S3_ENDPOINT")
    minio_access_key: str = Field(default="", alias="S3_ACCESS_KEY")
    minio_secret_key: str = Field(default="", alias="S3_SECRET_KEY")
    minio_bucket: str = Field(default="labbox-assets", alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")
    minio_auto_init: bool = Field(default=False, alias="MINIO_AUTO_INIT")
    storage_health_enabled: bool = Field(default=False, alias="STORAGE_HEALTH_ENABLED")

    @property
    def host(self) -> str:
        return self.base_url.host or "lab.aismallbizguru.com"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
