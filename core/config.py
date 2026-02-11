from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_env: str = "dev"
    secret_key: str = "change-me"


def get_database_url() -> str:
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    # Streamlit secrets fallback at runtime
    try:
        import streamlit as st

        return st.secrets["DATABASE_URL"]
    except Exception:
        return "postgresql+psycopg2://postgres:postgres@localhost:5432/run_season_command"


def get_settings() -> Settings:
    return Settings(
        database_url=get_database_url(),
        app_env=os.getenv("APP_ENV", "dev"),
        secret_key=os.getenv("SECRET_KEY", "change-me"),
    )
