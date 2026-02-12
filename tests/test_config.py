"""Tests for configuration module."""

from __future__ import annotations

from core.config import Settings, get_database_url, get_settings, _ENV_PROFILES


def test_settings_dataclass():
    s = Settings(database_url="postgres://localhost/test")
    assert s.database_url == "postgres://localhost/test"
    assert s.app_env == "dev"
    assert s.secret_key == "change-me"
    assert s.jwt_algorithm == "HS256"
    assert s.default_page_size == 50


def test_settings_frozen():
    s = Settings(database_url="x")
    try:
        s.database_url = "y"
        assert False, "Should raise"
    except AttributeError:
        pass


def test_settings_is_production():
    s = Settings(database_url="x", app_env="production")
    assert s.is_production is True
    assert s.is_dev is False


def test_settings_is_dev():
    s = Settings(database_url="x", app_env="dev")
    assert s.is_dev is True
    assert s.is_production is False


def test_get_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://from-env/db")
    assert get_database_url() == "postgres://from-env/db"


def test_get_database_url_default(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Will fall through to default when streamlit is not configured
    url = get_database_url()
    assert "postgresql" in url


def test_get_settings_uses_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://test/db")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "super-secret")
    s = get_settings()
    assert s.database_url == "postgres://test/db"
    assert s.app_env == "production"
    assert s.secret_key == "super-secret"


def test_env_profiles_exist():
    assert "dev" in _ENV_PROFILES
    assert "staging" in _ENV_PROFILES
    assert "production" in _ENV_PROFILES


def test_production_profile_has_tighter_risk():
    assert _ENV_PROFILES["production"]["guardrail_risk_max"] == 0.80


def test_dev_profile_debug_logging():
    assert _ENV_PROFILES["dev"]["log_level"] == "DEBUG"


def test_settings_jwt_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://test/db")
    monkeypatch.setenv("JWT_SECRET", "my-jwt-secret")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")
    s = get_settings()
    assert s.jwt_secret == "my-jwt-secret"
    assert s.jwt_expire_minutes == 60


def test_settings_profile_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://test/db")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("JWT_EXPIRE_MINUTES", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    s = get_settings()
    # dev profile should set jwt_expire_minutes=1440 and log_level=DEBUG
    assert s.jwt_expire_minutes == 1440
    assert s.log_level == "DEBUG"
