"""Tests for application settings."""

import pytest
from src.config.settings import Settings


def test_settings_reads_mongodb_url_from_env(monkeypatch):
    """Settings picks up MONGODB_URL from the environment."""
    monkeypatch.setenv("MONGODB_URL", "mongodb://user:pass@myhost:27017/")
    settings = Settings()
    assert settings.mongodb_url == "mongodb://user:pass@myhost:27017/"


def test_settings_has_default_mongodb_database():
    """Settings provides a default database name when MONGODB_DATABASE is unset."""
    settings = Settings()
    assert settings.mongodb_database == "feedback"


def test_settings_reads_mongodb_database_from_env(monkeypatch):
    """Settings picks up MONGODB_DATABASE from the environment."""
    monkeypatch.setenv("MONGODB_DATABASE", "my_custom_db")
    settings = Settings()
    assert settings.mongodb_database == "my_custom_db"


def test_settings_has_default_cors_origins():
    """Settings provides localhost defaults for CORS when unset."""
    settings = Settings()
    assert "http://localhost:3000" in settings.cors_origins
    assert "http://localhost:8000" in settings.cors_origins


def test_settings_reads_cors_origins_from_env(monkeypatch):
    """Settings reads CORS_ORIGINS as a JSON array from the environment."""
    monkeypatch.setenv("CORS_ORIGINS", '["https://myapp.example.com"]')
    settings = Settings()
    assert settings.cors_origins == ["https://myapp.example.com"]
