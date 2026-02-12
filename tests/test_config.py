"""Tests for configuration module."""

from __future__ import annotations

from core.config import Settings, get_database_url, get_settings


def test_settings_dataclass():
    s = Settings(database_url="postgres://localhost/test")
    assert s.database_url == "postgres://localhost/test"
    assert s.app_env == "dev"
    assert s.secret_key == "change-me"


def test_settings_frozen():
    s = Settings(database_url="x")
    try:
        s.database_url = "y"
        assert False, "Should raise"
    except AttributeError:
        pass


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
