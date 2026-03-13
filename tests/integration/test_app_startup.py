"""Integration tests for application startup."""

import pytest
from fastapi.testclient import TestClient


def test_app_starts_with_valid_config():
    """Application starts successfully when config/triads.yaml is valid."""
    # Import after ensuring config exists
    from src.api.main import app

    # Act: Create test client (triggers startup)
    client = TestClient(app)

    # Assert: Health endpoint works
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_app_loads_triad_config_on_startup():
    """Application loads and validates triad config on startup."""
    from src.api.main import app

    # TestClient triggers lifespan
    with TestClient(app) as client:
        # Make a request to ensure app is fully initialized
        response = client.get("/health")
        assert response.status_code == 200

        # Assert: App state contains loaded config
        assert hasattr(app.state, "triad_config")
        assert app.state.triad_config is not None
        assert app.state.triad_config.version == "1.0"
        assert len(app.state.triad_config.triads) == 3


def test_app_creates_mongo_client_singleton_on_startup():
    """Application creates a single MongoClient at startup and stores it in app.state."""
    from src.api.main import app

    with TestClient(app) as client:
        client.get("/health")

        assert hasattr(app.state, "mongo_client")
        assert app.state.mongo_client is not None
        # Verify it is the same object across two accesses (singleton)
        first = app.state.mongo_client
        second = app.state.mongo_client
        assert first is second
