"""Integration tests for the dashboard API and UI page."""

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient


@pytest.fixture
def test_db():
    client = MongoClient("mongodb://admin:password@localhost:27017/")
    db = client["test_feedback_dashboard"]
    db.stories.delete_many({})
    yield db
    db.stories.delete_many({})
    client.close()


@pytest.fixture
def api_client(test_db):
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_storage

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_storage, None)


# ── Dashboard HTML page ────────────────────────────────────────────────────────


def test_dashboard_page_returns_html(api_client):
    """GET /dashboard returns 200 HTML."""
    response = api_client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_dashboard_page_links_to_submission_form(api_client):
    """Dashboard page has a link to the story submission form."""
    response = api_client.get("/dashboard")
    assert 'href="/"' in response.text or "Submit" in response.text


def test_dashboard_page_includes_htmx(api_client):
    """Dashboard page loads HTMX."""
    response = api_client.get("/dashboard")
    assert "htmx" in response.text.lower()


# ── Dashboard API ──────────────────────────────────────────────────────────────


def test_dashboard_api_returns_json(api_client):
    """GET /api/dashboard returns JSON with expected keys."""
    response = api_client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert "total_stories" in body
    assert "top_themes" in body
    assert "top_entities" in body


def test_dashboard_api_empty_store(api_client):
    """GET /api/dashboard with no stories returns zeros."""
    response = api_client.get("/api/dashboard")
    body = response.json()
    assert body["total_stories"] == 0
    assert body["top_themes"] == []
    assert body["top_entities"] == []


def test_dashboard_api_reflects_submitted_stories(test_db, api_client):
    """Stats reflect stories that have been submitted."""
    # Submit a story
    api_client.post(
        "/api/stories",
        json={
            "story_text": "The CI pipeline kept failing and blocked our team repeatedly. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
                {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
                {"triad_id": "value_character", "x": 0.2, "y": 0.7},
            ],
        },
    )

    response = api_client.get("/api/dashboard")
    body = response.json()
    assert body["total_stories"] == 1


def test_dashboard_api_csv_export(api_client):
    """GET /api/dashboard?format=csv returns text/csv content."""
    response = api_client.get("/api/dashboard?format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]


def test_dashboard_api_json_export(api_client):
    """GET /api/dashboard?format=json returns application/json."""
    response = api_client.get("/api/dashboard?format=json")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


def test_dashboard_api_date_filter(test_db, api_client):
    """from_date param excludes older stories."""
    # Submit a story first
    api_client.post(
        "/api/stories",
        json={
            "story_text": "The CI pipeline kept failing and blocked our team repeatedly. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
                {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
                {"triad_id": "value_character", "x": 0.2, "y": 0.7},
            ],
        },
    )

    # Filter to far future — should return 0
    response = api_client.get("/api/dashboard?from_date=2030-01-01T00:00:00Z")
    assert response.status_code == 200
    assert response.json()["total_stories"] == 0
