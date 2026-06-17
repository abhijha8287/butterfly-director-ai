from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Butterfly Director AI"
    env: Literal["development", "testing", "production"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/v1"

    secret_key: str = Field(default="CHANGE-ME-INSECURE-DEV-SECRET-KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    auth_enabled: bool = False

    database_url: str = Field(
        default="postgresql+asyncpg://butterfly:butterfly@localhost:5432/butterfly_director"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://butterfly:butterfly@localhost:5432/butterfly_director"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 10

    redis_url: str = Field(default="redis://localhost:6379/0")

    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    log_level: str = "INFO"
    log_json: bool = False

    rate_limit_per_minute: int = 120

    default_page_size: int = 20
    max_page_size: int = 100

    # DashScope (Alibaba Cloud Model Studio) - international endpoint, single account
    # key shared across Qwen / Wan / CosyVoice per Alibaba's actual auth model.
    dashscope_base_url: str = Field(default="https://dashscope-intl.aliyuncs.com")
    dashscope_ws_base_url: str = Field(default="wss://dashscope-intl.aliyuncs.com")
    dashscope_api_key: str = Field(default="")

    qwen_model: str = Field(default="qwen-plus")

    wan_model: str = Field(default="wan2.6-t2v")
    wan_video_size: str = Field(default="1280*720")
    wan_video_duration_seconds: int = Field(default=5)

    cosyvoice_model: str = Field(default="cosyvoice-v3-flash")
    cosyvoice_default_voice: str = Field(default="longanyang")

    # Strategy-pattern provider selection - business logic never depends on a vendor
    # directly, only on the VideoGenerationProvider / VoiceGenerationProvider /
    # MusicGenerationProvider interfaces in app/integrations/providers/base.py.
    video_provider: Literal["wan", "happyhorse"] = Field(default="wan")
    voice_provider: Literal["dashscope", "happyhorse"] = Field(default="dashscope")
    music_provider: Literal["happyhorse", "none"] = Field(default="none")

    # HappyHorseProvider is a generic, vendor-agnostic adapter - isolated HTTP details
    # behind this config so a real provider (Runway, Kling, Veo, ElevenLabs, PlayHT...)
    # can be plugged in later without touching any agent/service code. Empty by default;
    # selecting "happyhorse" without configuring these raises ProviderNotConfiguredError.
    happyhorse_base_url: str = Field(default="")
    happyhorse_api_key: str = Field(default="")

    provider_poll_interval_seconds: float = Field(default=15.0)
    provider_poll_timeout_seconds: float = Field(default=600.0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
