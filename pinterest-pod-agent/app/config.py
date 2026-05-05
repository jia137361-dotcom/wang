import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    The provided Volcengine Ark values are kept as internal-test defaults and
    can be overridden by environment variables in deployed environments.
    """

    app_name: str = "Pinterest POD Agent"
    api_key: str = Field(
        default="",
        validation_alias="API_KEY",
        description="API key for securing endpoints. Leave empty to disable auth.",
    )
    database_url: str = Field(
        default="",
        validation_alias="DATABASE_URL",
    )

    volc_api_key: str = Field(
        default="",
        validation_alias="VOLC_API_KEY",
    )
    volc_base_url: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3",
        validation_alias="VOLC_BASE_URL",
    )
    volc_model: str = Field(
        default="ark-4136acc2-b228-4b02-8bc9-e46e3d3030a6-6430e",
        validation_alias="VOLC_MODEL",
    )
    volc_timeout_seconds: float = Field(default=60.0, validation_alias="VOLC_TIMEOUT_SECONDS")
    volc_max_retries: int = Field(default=2, validation_alias="VOLC_MAX_RETRIES")

    adspower_base_url: str = Field(
        default="http://local.adspower.net:50325",
        validation_alias="ADSPOWER_BASE_URL",
    )
    adspower_api_key: str | None = Field(default=None, validation_alias="ADSPOWER_API_KEY")
    adspower_timeout_seconds: float = Field(default=30.0, validation_alias="ADSPOWER_TIMEOUT_SECONDS")
    upload_dir: str = Field(default="var/uploads", validation_alias="UPLOAD_DIR")
    max_upload_size_mb: int = Field(default=20, validation_alias="MAX_UPLOAD_SIZE_MB")
    scheduler_enabled: bool = Field(default=True, validation_alias="SCHEDULER_ENABLED")
    scheduler_timezone: str = Field(default="Asia/Shanghai", validation_alias="SCHEDULER_TIMEZONE")
    publish_interval_minutes: int = Field(default=30, validation_alias="PUBLISH_INTERVAL_MINUTES")
    scheduler_dry_run: bool = Field(default=False, validation_alias="SCHEDULER_DRY_RUN")
    redis_url: str = Field(default="redis://localhost:6379", validation_alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/0", validation_alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/1", validation_alias="CELERY_RESULT_BACKEND")
    fal_key: str | None = Field(default=None, validation_alias="FAL_KEY")
    video_provider_api_key: str | None = Field(default=None, validation_alias="VIDEO_PROVIDER_API_KEY")
    trend_provider_api_key: str | None = Field(default=None, validation_alias="TREND_PROVIDER_API_KEY")
    pinterest_api_key: str | None = Field(default=None, validation_alias="PINTEREST_API_KEY")
    pinterest_trends_enabled: bool = Field(default=False, validation_alias="PINTEREST_TRENDS_ENABLED")
    pinterest_trends_base_url: str = Field(
        default="https://api.pinterest.com/v5",
        validation_alias="PINTEREST_TRENDS_BASE_URL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.fal_key and not os.environ.get("FAL_KEY"):
        os.environ["FAL_KEY"] = settings.fal_key
    return settings
