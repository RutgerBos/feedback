"""Integration tests for the story submission UI."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ui_client():
    """TestClient for the app with no infrastructure dependencies."""
    from src.api.main import app

    with TestClient(app) as client:
        yield client


def test_root_returns_html(ui_client):
    """GET / returns an HTML page."""
    response = ui_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_page_has_story_textarea(ui_client):
    """GET / page contains a textarea for story text."""
    response = ui_client.get("/")
    assert "<textarea" in response.text


def test_page_has_triad_canvases_for_all_triads(ui_client):
    """GET / page has an SVG canvas for each of the 3 triads."""
    response = ui_client.get("/")
    for triad_id in ("workflow_nature", "understanding_quality", "value_character"):
        assert triad_id in response.text


def test_page_has_vertex_labels(ui_client):
    """GET / page shows the vertex labels from the triad config."""
    response = ui_client.get("/")
    # Spot-check one label per triad
    for label in ("Streamlined", "Intuitive", "Foundational"):
        assert label in response.text


def test_page_has_hidden_coordinate_inputs(ui_client):
    """GET / page has hidden inputs for each triad's x and y coordinates."""
    response = ui_client.get("/")
    for triad_id in ("workflow_nature", "understanding_quality", "value_character"):
        assert f'name="{triad_id}_x"' in response.text
        assert f'name="{triad_id}_y"' in response.text


def test_triad_inputs_default_to_centre(ui_client):
    """Hidden triad coordinate inputs default to 0.5 (centre of triangle)."""
    response = ui_client.get("/")
    assert 'value="0.5"' in response.text


def test_form_targets_stories_endpoint(ui_client):
    """The submission form POSTs to /api/stories via HTMX."""
    response = ui_client.get("/")
    assert 'hx-post="/api/stories"' in response.text or 'action="/api/stories"' in response.text


def test_page_includes_htmx(ui_client):
    """GET / page loads HTMX."""
    response = ui_client.get("/")
    assert "htmx" in response.text.lower()
