"""Integration tests for stories API endpoint."""

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient


@pytest.fixture
def test_db():
    """Provide clean test database."""
    client = MongoClient("mongodb://admin:password@localhost:27017/")
    db = client["test_feedback_api"]
    db.stories.delete_many({})
    yield db
    db.stories.delete_many({})
    client.close()


@pytest.fixture
def api_client(test_db):
    """Provide a TestClient with storage overridden to use the test database."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_llm, get_storage
    from src.ports.llm import EntityExtraction, LLMPort

    from src.domain.models import SentimentAnalysis

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_themes(self, story_text: str) -> list:
            return []

        def extract_relationships(self, story_text: str) -> list:
            return []

        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)


def test_list_stories_rejects_invalid_pagination(test_db, api_client):
    """GET /api/stories rejects negative offset and out-of-range limit (1-100)."""
    client = api_client

    assert client.get("/api/stories?offset=-1").status_code == 422
    assert client.get("/api/stories?limit=0").status_code == 422
    assert client.get("/api/stories?limit=101").status_code == 422
    # offset has no upper bound — large page offsets are valid
    assert client.get("/api/stories?offset=10000").status_code == 200


def test_submit_story_via_api(test_db, api_client):
    """Can submit a story via POST /api/stories."""
    client = api_client

    response = client.post(
        "/api/stories",
        json={
            "story_text": "I had to restart the CI pipeline three times today because of flaky tests. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
                {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
                {"triad_id": "value_character", "x": 0.2, "y": 0.7},
            ],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "story_id" in data
    assert data["message"] == "Story submitted successfully"

    # Verify story was saved to database
    story = test_db.stories.find_one({"_id": data["story_id"]})
    assert story is not None
    assert "CI pipeline" in story["story_text"]


def test_submit_story_with_invalid_data(test_db, api_client):
    """Submitting invalid data returns 400."""
    client = api_client

    # Too short story
    response = client.post(
        "/api/stories",
        json={
            "story_text": "Too short",
            "triads": [
                {"triad_id": "t1", "x": 0.3, "y": 0.6},
                {"triad_id": "t2", "x": 0.5, "y": 0.4},
                {"triad_id": "t3", "x": 0.2, "y": 0.7},
            ],
        },
    )

    assert response.status_code == 422  # Pydantic validation error


def test_list_stories_returns_all_stories(test_db, api_client):
    """GET /api/stories returns all submitted stories."""
    client = api_client

    story_text = "Working on the new feature was a great collaborative experience. " * 2

    # Submit two stories
    for _ in range(2):
        client.post(
            "/api/stories",
            json={
                "story_text": story_text,
                "triads": [
                    {"triad_id": "workflow_nature", "x": 0.3, "y": 0.4},
                    {"triad_id": "understanding_quality", "x": 0.4, "y": 0.3},
                    {"triad_id": "value_character", "x": 0.5, "y": 0.2},
                ],
            },
        )

    response = client.get("/api/stories")

    assert response.status_code == 200
    data = response.json()
    assert len(data["stories"]) == 2
    assert data["total"] == 2


def test_list_stories_returns_empty_list_when_no_stories(test_db, api_client):
    """GET /api/stories returns empty list when no stories exist."""
    client = api_client

    response = client.get("/api/stories")

    assert response.status_code == 200
    data = response.json()
    assert data["stories"] == []
    assert data["total"] == 0


def test_list_stories_supports_pagination(test_db, api_client):
    """GET /api/stories supports limit and offset query params."""
    client = api_client

    story_text = "The CI system has improved significantly after the recent infrastructure changes. " * 2

    # Submit 3 stories
    for _ in range(3):
        client.post(
            "/api/stories",
            json={
                "story_text": story_text,
                "triads": [
                    {"triad_id": "workflow_nature", "x": 0.3, "y": 0.4},
                    {"triad_id": "understanding_quality", "x": 0.4, "y": 0.3},
                    {"triad_id": "value_character", "x": 0.5, "y": 0.2},
                ],
            },
        )

    response = client.get("/api/stories?limit=2&offset=0")
    assert response.status_code == 200
    assert len(response.json()["stories"]) == 2

    response = client.get("/api/stories?limit=2&offset=2")
    assert response.status_code == 200
    assert len(response.json()["stories"]) == 1


def test_submit_story_with_metadata(test_db, api_client):
    """Can submit a story with optional metadata (department, role, user_pseudonym)."""
    client = api_client

    response = client.post(
        "/api/stories",
        json={
            "story_text": "The deployment process has become much smoother after the recent automation improvements. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.8, "y": 0.1},
                {"triad_id": "understanding_quality", "x": 0.6, "y": 0.3},
                {"triad_id": "value_character", "x": 0.7, "y": 0.2},
            ],
            "metadata": {
                "department": "engineering",
                "role": "senior_developer",
                "user_pseudonym": "user_abc123"
            }
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "story_id" in data

    # Verify metadata was saved to database
    story = test_db.stories.find_one({"_id": data["story_id"]})
    assert story is not None
    assert story["metadata"]["department"] == "engineering"
    assert story["metadata"]["role"] == "senior_developer"
    assert story["metadata"]["user_pseudonym"] == "user_abc123"


def test_get_story_by_id(test_db, api_client):
    """GET /api/stories/{id} returns a story with all fields."""
    client = api_client

    # First submit a story
    submit_response = client.post(
        "/api/stories",
        json={
            "story_text": "The deployment pipeline finally works smoothly after months of effort. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.5, "y": 0.3},
                {"triad_id": "understanding_quality", "x": 0.4, "y": 0.4},
                {"triad_id": "value_character", "x": 0.3, "y": 0.5},
            ],
            "metadata": {"department": "engineering", "role": "developer"},
        },
    )
    story_id = submit_response.json()["story_id"]

    # Now retrieve it
    response = client.get(f"/api/stories/{story_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == story_id
    assert "deployment pipeline" in data["story_text"]
    assert len(data["triads"]) == 3
    assert data["metadata"]["department"] == "engineering"
    assert "timestamp" in data


def test_get_story_returns_404_for_unknown_id(test_db, api_client):
    """GET /api/stories/{id} returns 404 for a non-existent story."""
    client = api_client

    response = client.get("/api/stories/nonexistent-id-xyz")

    assert response.status_code == 404


def test_submit_story_triggers_entity_extraction(test_db):
    """Submitting a story triggers background entity extraction via FakeLLM."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_llm, get_storage
    from src.ports.llm import EntityExtraction, LLMPort

    from src.domain.models import SentimentAnalysis

    class FakeLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(
                entities=[{"name": "CI pipeline", "type": "tool"}],
            )

        def extract_themes(self, story_text: str) -> list:
            return []

        def extract_relationships(self, story_text: str) -> list:
            return []

        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/stories",
                json={
                    "story_text": "CI failures blocked our deployment repeatedly this sprint. " * 2,
                    "triads": [
                        {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
                        {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
                        {"triad_id": "value_character", "x": 0.2, "y": 0.7},
                    ],
                },
            )
            assert response.status_code == 201
            story_id = response.json()["story_id"]
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)

    # Background task should have run; verify extraction results in DB
    doc = test_db.stories.find_one({"_id": story_id})
    assert doc["processing_status"] == "processed"
    assert doc["entities"] == [{"name": "CI pipeline", "type": "tool"}]


def test_submit_story_rejects_unknown_triad_id(test_db, api_client):
    """POST /api/stories returns 400 when a triad_id is not in the loaded config."""
    client = api_client

    response = client.post(
        "/api/stories",
        json={
            "story_text": "The deployment pipeline failed twice before we caught the config issue. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
                {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
                {"triad_id": "phantom_triad", "x": 0.2, "y": 0.7},  # not in config
            ],
        },
    )

    assert response.status_code == 400
    assert "phantom_triad" in response.json()["detail"]


def test_submit_story_without_metadata(test_db, api_client):
    """Can submit a story without metadata - metadata is optional."""
    client = api_client

    # Submit story without metadata field at all
    response = client.post(
        "/api/stories",
        json={
            "story_text": "The new feature made my workflow much faster and more efficient today. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.9, "y": 0.05},
                {"triad_id": "understanding_quality", "x": 0.7, "y": 0.2},
                {"triad_id": "value_character", "x": 0.8, "y": 0.1},
            ],
            # No metadata field
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "story_id" in data

    # Verify story was saved without metadata
    story = test_db.stories.find_one({"_id": data["story_id"]})
    assert story is not None
    assert story["metadata"] is None


def test_submit_story_triggers_graph_node_creation(test_db):
    """Submitting a story triggers save_story_node() as a background task."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    saved_nodes = []

    from src.domain.models import SentimentAnalysis

    class FakeLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_themes(self, story_text: str) -> list:
            return []

        def extract_relationships(self, story_text: str) -> list:
            return []

        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

    class CapturingGraph(GraphPort):
        def save_story_node(self, story_id: str, triads, timestamp: str) -> None:
            saved_nodes.append({"story_id": story_id, "triads": triads})

        def save_entity_nodes(self, story_id: str, entities: list) -> None:
            pass

        def save_theme_nodes(self, story_id: str, themes: list) -> None:
            pass

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    app.dependency_overrides[get_graph] = lambda: CapturingGraph()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/stories",
                json={
                    "story_text": "CI failures blocked our deployment repeatedly this sprint. " * 2,
                    "triads": [
                        {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
                        {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
                        {"triad_id": "value_character", "x": 0.2, "y": 0.7},
                    ],
                },
            )
            assert response.status_code == 201
            story_id = response.json()["story_id"]
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)

    assert len(saved_nodes) == 1
    assert saved_nodes[0]["story_id"] == story_id
    assert len(saved_nodes[0]["triads"]) == 3
