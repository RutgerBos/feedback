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


def test_settings_has_default_neo4j_url():
    """Settings provides a default Neo4j URL for local development."""
    settings = Settings()
    assert settings.neo4j_url == "bolt://localhost:7687"


def test_settings_reads_neo4j_url_from_env(monkeypatch):
    """Settings picks up NEO4J_URL from the environment."""
    monkeypatch.setenv("NEO4J_URL", "bolt://neo4j-host:7687")
    settings = Settings()
    assert settings.neo4j_url == "bolt://neo4j-host:7687"


def test_settings_has_default_neo4j_credentials():
    """Settings provides default Neo4j user and password."""
    settings = Settings()
    assert settings.neo4j_user == "neo4j"
    assert settings.neo4j_password == "password"


def test_settings_reads_neo4j_credentials_from_env(monkeypatch):
    """Settings picks up NEO4J_USER and NEO4J_PASSWORD from the environment."""
    monkeypatch.setenv("NEO4J_USER", "admin")
    monkeypatch.setenv("NEO4J_PASSWORD", "s3cret")
    settings = Settings()
    assert settings.neo4j_user == "admin"
    assert settings.neo4j_password == "s3cret"
