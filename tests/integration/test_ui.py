"""Integration tests for the story submission UI."""

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient


@pytest.fixture
def ui_client():
    """TestClient for the app with no infrastructure dependencies."""
    from src.api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_db():
    """Provide a clean test database."""
    client = MongoClient("mongodb://admin:password@localhost:27017/")
    db = client["test_feedback_ui"]
    db.stories.delete_many({})
    yield db
    db.stories.delete_many({})
    client.close()


@pytest.fixture
def submit_client(test_db):
    """TestClient with real MongoDB wired up for submit tests."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_storage

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_storage, None)


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


def test_form_targets_ui_submit_endpoint(ui_client):
    """The submission form POSTs to /ui/submit via HTMX."""
    response = ui_client.get("/")
    assert 'hx-post="/ui/submit"' in response.text


def test_page_includes_htmx(ui_client):
    """GET / page loads HTMX."""
    response = ui_client.get("/")
    assert "htmx" in response.text.lower()


# ── Form submission ────────────────────────────────────────────────────────────

_VALID_FORM = {
    "story_text": "The CI pipeline kept failing and blocked our team for three days in a row.",
    "workflow_nature_x": "0.3",
    "workflow_nature_y": "0.6",
    "understanding_quality_x": "0.5",
    "understanding_quality_y": "0.4",
    "value_character_x": "0.2",
    "value_character_y": "0.7",
}


def test_submit_valid_story_returns_confirmation(submit_client):
    """POST /ui/submit with valid data returns HTML confirmation fragment."""
    response = submit_client.post("/ui/submit", data=_VALID_FORM)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "submitted" in response.text.lower() or "thank you" in response.text.lower()


def test_submit_short_story_returns_error(submit_client):
    """POST /ui/submit with story shorter than 50 chars returns 400 HTML error."""
    form = {**_VALID_FORM, "story_text": "Too short."}
    response = submit_client.post("/ui/submit", data=form)
    assert response.status_code == 400
    assert "text/html" in response.headers["content-type"]


def test_submit_returns_story_id_in_confirmation(submit_client):
    """POST /ui/submit confirmation fragment contains the story ID."""
    response = submit_client.post("/ui/submit", data=_VALID_FORM)
    assert response.status_code == 200
    assert "Reference:" in response.text


def test_submit_stores_signification_not_bare_triads(submit_client, test_db):
    """POST /ui/submit stores signification.responses, not bare triads[], on the new story."""
    response = submit_client.post("/ui/submit", data=_VALID_FORM)
    assert response.status_code == 200

    doc = test_db.stories.find_one({})
    assert doc is not None
    assert doc.get("signification") is not None
    responses = doc["signification"]["responses"]
    assert len(responses) == 3
    signifier_ids = {r["signifier_id"] for r in responses}
    assert signifier_ids == {"workflow_nature", "understanding_quality", "value_character"}
    # triads list should be empty — coordinates live in signification now
    assert doc.get("triads") == []


def test_submit_triggers_background_processing(test_db):
    """POST /ui/submit schedules entity extraction as a background task."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class FakeLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[{"name": "CI pipeline", "type": "tool"}])

        def extract_themes(self, story_text: str) -> list:
            return []

        def extract_relationships(self, story_text: str) -> list:
            return []

        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

        def synthesize_insights(self, context):  # type: ignore[override]
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")

        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")

    class NoOpGraph(GraphPort):
        def save_story_node(self, story_id, triads, timestamp): pass
        def save_entity_nodes(self, story_id, entities): pass
        def save_theme_nodes(self, story_id, themes): pass
        def save_proximity_relationships(self, story_id, pairs): pass
        def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None): return []
        def count_stories_by_entity(self, entity_name): return 0
        def find_themes_ranked(self, limit, from_date=None, to_date=None): return []
        def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None): return []
        def count_stories_by_theme(self, theme_name): return 0
        def find_entity_correlations(self, limit, threshold=0.0, entity_type=None): return []
        def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0): return []
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []
        def find_story_communities(self, triad_id): return []

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    app.dependency_overrides[get_graph] = lambda: NoOpGraph()
    try:
        with TestClient(app) as client:
            response = client.post("/ui/submit", data=_VALID_FORM)
            assert response.status_code == 200
            story_id = test_db.stories.find_one({})["_id"]
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)

    doc = test_db.stories.find_one({"_id": story_id})
    assert doc["entity_status"] == "processed", (
        "entity extraction must run as a background task after UI submit"
    )
