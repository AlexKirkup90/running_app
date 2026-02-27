from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/run_season_command"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    log_level: str = "INFO"
    request_id_header_name: str = "X-Request-ID"
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    streamlit_database_url: Optional[str] = Field(default=None, alias="STREAMLIT_DATABASE_URL")

    secret_key: str = "change-me"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    cors_origins_raw: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    redis_url: str = "redis://localhost:6379/0"
    cache_prefix: str = "run-season-command"
    cache_default_ttl_seconds: int = 3600
    analytics_cache_ttl_seconds: int = 3600
    workload_cache_ttl_seconds: int = 3600
    rate_limit_enabled: bool = True
    rate_limit_storage_uri: str = "memory://"
    auth_token_rate_limit: str = "10/minute"
    write_endpoint_rate_limit: str = "120/minute"
    webhook_rate_limit: str = "240/minute"
    integration_persist_retry_attempts: int = 2

    event_training_log_created: str = "training_log.created"
    strava_provider_name: str = "strava"
    garmin_provider_name: str = "garmin"

    readiness_green_min: float = 4.0
    readiness_amber_min: float = 3.0

    intervention_action_monitor: str = "monitor"
    intervention_action_recovery_week: str = "recovery_week"
    intervention_action_contact_athlete: str = "contact_athlete"
    intervention_action_taper_week: str = "taper_week"

    intervention_low_readiness_threshold: float = 2.8
    intervention_low_adherence_threshold: float = 0.6
    intervention_no_recent_logs_days: int = 4
    intervention_event_proximity_days: int = 14
    intervention_guardrail_risk_max: float = 0.85

    intervention_base_risk: float = 0.2
    intervention_base_confidence: float = 0.75
    intervention_low_readiness_risk_bump: float = 0.25
    intervention_no_recent_logs_risk_bump: float = 0.10
    intervention_low_adherence_confidence_bump: float = 0.05

    @property
    def cors_origins(self) -> list[str]:
        raw = (self.cors_origins_raw or "").strip()
        if not raw:
            return ["http://localhost:5173"]
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.streamlit_database_url:
            return self.streamlit_database_url
        try:
            import streamlit as st

            return str(st.secrets["DATABASE_URL"])
        except Exception:
            return DEFAULT_DB_URL


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_database_url() -> str:
    return get_settings().resolved_database_url
