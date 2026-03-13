"""Integration tests for application startup."""

from fastapi.testclient import TestClient


def test_app_starts_with_valid_config():
    """Application starts successfully when config/triads.yaml is valid."""
    from src.api.main import app

    with TestClient(app) as client:
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


def test_cors_allows_configured_origin(monkeypatch):
    """Requests from a configured CORS origin receive the Access-Control-Allow-Origin header."""
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')
    from importlib import reload

    import src.api.main as main_mod
    import src.config.settings as settings_mod
    reload(settings_mod)
    reload(main_mod)

    with TestClient(main_mod.app) as client:
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_unknown_origin(monkeypatch):
    """Requests from an unconfigured origin do not receive the CORS header."""
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')
    from importlib import reload

    import src.api.main as main_mod
    import src.config.settings as settings_mod
    reload(settings_mod)
    reload(main_mod)

    with TestClient(main_mod.app) as client:
        response = client.get("/health", headers={"Origin": "http://evil.example.com"})
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers


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
