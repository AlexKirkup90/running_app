"""Application configuration with environment-specific profiles.

Supports dev, staging, and production environments via APP_ENV.
All values can be overridden by environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Immutable application settings resolved from environment."""

    database_url: str
    app_env: str = "dev"
    secret_key: str = "change-me"
    jwt_secret: str = "jwt-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    log_level: str = "INFO"

    # Risk thresholds (configurable per environment)
    guardrail_risk_max: float = 0.85
    readiness_green_threshold: float = 4.0
    readiness_amber_threshold: float = 3.0
    intervention_cooldown_hours: int = 24
    sla_warn_hours: int = 24
    sla_critical_hours: int = 72

    # Pagination
    default_page_size: int = 50
    max_page_size: int = 200

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


# -- Environment profiles --

_ENV_PROFILES: dict[str, dict] = {
    "dev": {
        "log_level": "DEBUG",
        "jwt_expire_minutes": 1440,
    },
    "staging": {
        "log_level": "INFO",
        "jwt_expire_minutes": 480,
    },
    "production": {
        "log_level": "WARNING",
        "jwt_expire_minutes": 240,
        "guardrail_risk_max": 0.80,
    },
}


def get_database_url() -> str:
    """Resolve database URL from env var, Streamlit secrets, or local default.

    Resolution order:
    1. DATABASE_URL environment variable
    2. Streamlit secrets (`.streamlit/secrets.toml`)
    3. Local default for common dev setups
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    try:
        import streamlit as st

        return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    # Sensible local-dev default.  Copy .streamlit/secrets.toml.example →
    # .streamlit/secrets.toml and adjust if your setup differs.
    return "postgresql+psycopg2://localhost:5432/runseason"


def get_settings() -> Settings:
    """Build Settings by merging environment profile with env-var overrides."""
    app_env = os.getenv("APP_ENV", "dev")
    profile = _ENV_PROFILES.get(app_env, _ENV_PROFILES["dev"])

    return Settings(
        database_url=get_database_url(),
        app_env=app_env,
        secret_key=os.getenv("SECRET_KEY", "change-me"),
        jwt_secret=os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "jwt-change-me")),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", str(profile.get("jwt_expire_minutes", 480)))),
        log_level=os.getenv("LOG_LEVEL", profile.get("log_level", "INFO")),
        guardrail_risk_max=float(os.getenv("GUARDRAIL_RISK_MAX", str(profile.get("guardrail_risk_max", 0.85)))),
        readiness_green_threshold=float(os.getenv("READINESS_GREEN_THRESHOLD", "4.0")),
        readiness_amber_threshold=float(os.getenv("READINESS_AMBER_THRESHOLD", "3.0")),
        intervention_cooldown_hours=int(os.getenv("INTERVENTION_COOLDOWN_HOURS", "24")),
        sla_warn_hours=int(os.getenv("SLA_WARN_HOURS", "24")),
        sla_critical_hours=int(os.getenv("SLA_CRITICAL_HOURS", "72")),
        default_page_size=int(os.getenv("DEFAULT_PAGE_SIZE", "50")),
        max_page_size=int(os.getenv("MAX_PAGE_SIZE", "200")),
    )
