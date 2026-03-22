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
    """Provide a TestClient with storage, LLM, and graph overridden to use test doubles."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

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
        def save_story_node(self, story_id: str, triads, timestamp: str) -> None:
            pass

        def save_entity_nodes(self, story_id: str, entities: list) -> None:
            pass

        def save_theme_nodes(self, story_id: str, themes: list) -> None:
            pass

        def save_proximity_relationships(self, story_id: str, pairs: list) -> None:
            pass

        def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int, from_date=None, to_date=None) -> list:
            return []

        def count_stories_by_entity(self, entity_name: str) -> int:
            return 0

        def find_themes_ranked(self, limit, from_date=None, to_date=None):
            return []

        def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None):
            return []

        def count_stories_by_theme(self, theme_name):
            return 0
        def find_entity_correlations(self, limit, threshold=0.0, entity_type=None):
            return []

        def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0):
            return []
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []

        def find_story_communities(self, triad_id):
            return []


    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: NoOpGraph()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


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
            "signification": {
                "responses": [
                    {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
                    {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
                    {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.2, "y": 0.7}},
                ]
            },
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


def test_submit_story_rejects_v1_triads(test_db, api_client):
    """POST /api/stories returns 422 when old V1 triads field is non-empty."""
    response = api_client.post(
        "/api/stories",
        json={
            "story_text": "I had to restart the CI pipeline three times today because of flaky tests. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
            ],
        },
    )
    assert response.status_code == 422


def test_submit_story_with_invalid_data(test_db, api_client):
    """Submitting invalid data returns 400."""
    client = api_client

    # Too short story
    response = client.post(
        "/api/stories",
        json={
            "story_text": "Too short",
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
                "signification": {
                    "responses": [
                        {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.4}},
                        {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.4, "y": 0.3}},
                        {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.5, "y": 0.2}},
                    ]
                },
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
                "signification": {
                    "responses": [
                        {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.4}},
                        {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.4, "y": 0.3}},
                        {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.5, "y": 0.2}},
                    ]
                },
            },
        )

    response = client.get("/api/stories?limit=2&offset=0")
    assert response.status_code == 200
    assert len(response.json()["stories"]) == 2

    response = client.get("/api/stories?limit=2&offset=2")
    assert response.status_code == 200
    assert len(response.json()["stories"]) == 1


def test_submit_story_with_metadata(test_db, api_client):
    """Can submit a story with optional context and participant fields."""
    client = api_client

    response = client.post(
        "/api/stories",
        json={
            "story_text": "The deployment process has become much smoother after the recent automation improvements. " * 2,
            "signification": {
                "responses": [
                    {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.8, "y": 0.1}},
                    {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.6, "y": 0.3}},
                    {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.7, "y": 0.2}},
                ]
            },
            "context": {"department": "engineering", "role": "senior_developer", "tool_context": None},
            "participant": {"user_pseudonym": "user_abc123"},
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "story_id" in data

    # Verify context and participant were saved to database
    story = test_db.stories.find_one({"_id": data["story_id"]})
    assert story is not None
    assert story["context"]["department"] == "engineering"
    assert story["participant"]["user_pseudonym"] == "user_abc123"


def test_get_story_by_id(test_db, api_client):
    """GET /api/stories/{id} returns a story with all fields."""
    client = api_client

    # First submit a story
    submit_response = client.post(
        "/api/stories",
        json={
            "story_text": "The deployment pipeline finally works smoothly after months of effort. " * 2,
            "signification": {
                "responses": [
                    {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.5, "y": 0.3}},
                    {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.4, "y": 0.4}},
                    {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.3, "y": 0.5}},
                ]
            },
        },
    )
    story_id = submit_response.json()["story_id"]

    # Now retrieve it
    response = client.get(f"/api/stories/{story_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == story_id
    assert "deployment pipeline" in data["story_text"]
    assert "timestamp" in data
    assert data["signification"] is not None
    assert len(data["signification"]["responses"]) == 3
    assert data["signification"]["responses"][0]["signifier_id"] == "workflow_nature"


def test_get_story_returns_404_for_unknown_id(test_db, api_client):
    """GET /api/stories/{id} returns 404 for a non-existent story."""
    client = api_client

    response = client.get("/api/stories/nonexistent-id-xyz")

    assert response.status_code == 404


def test_submit_story_triggers_entity_extraction(test_db):
    """Submitting a story triggers background entity extraction via FakeLLM."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

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

        def synthesize_insights(self, context):  # type: ignore[override]
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


    class NoOpGraph(GraphPort):
        def save_story_node(self, story_id: str, triads, timestamp: str) -> None:
            pass

        def save_entity_nodes(self, story_id: str, entities: list) -> None:
            pass

        def save_theme_nodes(self, story_id: str, themes: list) -> None:
            pass

        def save_proximity_relationships(self, story_id: str, pairs: list) -> None:
            pass

        def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int, from_date=None, to_date=None) -> list:
            return []

        def count_stories_by_entity(self, entity_name: str) -> int:
            return 0

        def find_themes_ranked(self, limit, from_date=None, to_date=None):
            return []

        def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None):
            return []

        def count_stories_by_theme(self, theme_name):
            return 0
        def find_entity_correlations(self, limit, threshold=0.0, entity_type=None):
            return []

        def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0):
            return []
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []

        def find_story_communities(self, triad_id):
            return []


    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    app.dependency_overrides[get_graph] = lambda: NoOpGraph()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/stories",
                json={
                    "story_text": "CI failures blocked our deployment repeatedly this sprint. " * 2,
                    "signification": {
                        "responses": [
                            {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
                            {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
                            {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.2, "y": 0.7}},
                        ]
                    },
                },
            )
            assert response.status_code == 201
            story_id = response.json()["story_id"]
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)

    # Background task should have run; verify extraction results in DB
    doc = test_db.stories.find_one({"_id": story_id})
    assert doc["entity_status"] == "processed"
    assert doc["entities"] == [{"name": "CI pipeline", "type": "tool"}]


def test_submit_story_rejects_unknown_triad_id(test_db, api_client):
    """POST /api/stories returns 400 when a signifier_id is not in the loaded config."""
    client = api_client

    response = client.post(
        "/api/stories",
        json={
            "story_text": "The deployment pipeline failed twice before we caught the config issue. " * 2,
            "signification": {
                "responses": [
                    {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
                    {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
                    {"kind": "triad", "signifier_id": "phantom_triad", "coordinates": {"x": 0.2, "y": 0.7}},  # not in config
                ]
            },
        },
    )

    assert response.status_code == 400
    assert "phantom_triad" in response.json()["detail"]


def test_submit_story_without_metadata(test_db, api_client):
    """Can submit a story without metadata - metadata is optional."""
    client = api_client

    # Submit story without context field at all
    response = client.post(
        "/api/stories",
        json={
            "story_text": "The new feature made my workflow much faster and more efficient today. " * 2,
            "signification": {
                "responses": [
                    {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.9, "y": 0.05}},
                    {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.7, "y": 0.2}},
                    {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.8, "y": 0.1}},
                ]
            },
            # No context or participant fields
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "story_id" in data

    # Verify story was saved without context
    story = test_db.stories.find_one({"_id": data["story_id"]})
    assert story is not None
    assert story.get("context") is None


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

        def synthesize_insights(self, context):  # type: ignore[override]
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


    class CapturingGraph(GraphPort):
        def save_story_node(self, story_id: str, triads, timestamp: str) -> None:
            saved_nodes.append({"story_id": story_id, "triads": triads})

        def save_entity_nodes(self, story_id: str, entities: list) -> None:
            pass

        def save_theme_nodes(self, story_id: str, themes: list) -> None:
            pass

        def save_proximity_relationships(self, story_id: str, pairs: list) -> None:
            pass

        def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int, from_date=None, to_date=None) -> list:
            return []

        def count_stories_by_entity(self, entity_name: str) -> int:
            return 0

        def find_themes_ranked(self, limit, from_date=None, to_date=None):
            return []

        def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None):
            return []

        def count_stories_by_theme(self, theme_name):
            return 0
        def find_entity_correlations(self, limit, threshold=0.0, entity_type=None):
            return []

        def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0):
            return []
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []

        def find_story_communities(self, triad_id):
            return []


    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    app.dependency_overrides[get_graph] = lambda: CapturingGraph()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/stories",
                json={
                    "story_text": "CI failures blocked our deployment repeatedly this sprint. " * 2,
                    "signification": {
                        "responses": [
                            {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
                            {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
                            {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.2, "y": 0.7}},
                        ]
                    },
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


def test_reprocess_unknown_story_returns_404(api_client):
    """POST /api/stories/{id}/reprocess returns 404 for non-existent story."""
    response = api_client.post("/api/stories/does-not-exist/reprocess")
    assert response.status_code == 404


def test_reprocess_existing_story_returns_202(api_client):
    """POST /api/stories/{id}/reprocess returns 202 for existing story."""
    submit = api_client.post(
        "/api/stories",
        json={
            "story_text": "CI failures blocked our deployment repeatedly this sprint. " * 2,
            "signification": {
                "responses": [
                    {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
                    {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
                    {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.2, "y": 0.7}},
                ]
            },
        },
    )
    story_id = submit.json()["story_id"]
    response = api_client.post(f"/api/stories/{story_id}/reprocess")
    assert response.status_code == 202


def test_get_story_returns_422_for_v1_story(test_db, api_client):
    """GET /api/stories/{id} returns 422 for a V1 story (no signification)."""
    import uuid
    from datetime import datetime, UTC

    story_id = str(uuid.uuid4())
    test_db.stories.insert_one({
        "_id": story_id,
        "story_text": "A legacy story with the old V1 format stored in the database.",
        "triads": [{"triad_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}}],
        "schema_version": 1,
        "processing_status": "processed",
        "timestamp": datetime.now(UTC),
    })

    response = api_client.get(f"/api/stories/{story_id}")
    assert response.status_code == 422
    assert "V1" in response.json()["detail"]


def test_list_stories_excludes_v1_stories(test_db, api_client):
    """GET /api/stories filters out V1 stories (no signification)."""
    import uuid
    from datetime import datetime, UTC

    # Insert a V1 story directly
    v1_id = str(uuid.uuid4())
    test_db.stories.insert_one({
        "_id": v1_id,
        "story_text": "A legacy story with the old V1 format stored in the database.",
        "triads": [{"triad_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}}],
        "schema_version": 1,
        "processing_status": "processed",
        "timestamp": datetime.now(UTC),
    })

    # Submit a V2 story via the API
    api_client.post(
        "/api/stories",
        json={
            "story_text": "Working on the new feature was a great collaborative experience. " * 2,
            "signification": {"responses": []},
        },
    )

    response = api_client.get("/api/stories")
    assert response.status_code == 200
    data = response.json()
    returned_ids = [s["id"] for s in data["stories"]]
    assert v1_id not in returned_ids
    assert len(data["stories"]) == 1


def test_submit_story_rejects_duplicate_signifier_ids(test_db, api_client):
    """POST /api/stories returns 422 for duplicate signifier_ids in responses."""
    response = api_client.post(
        "/api/stories",
        json={
            "story_text": "I had to restart the CI pipeline three times today because of flaky tests. " * 2,
            "signification": {
                "responses": [
                    {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
                    {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.5, "y": 0.4}},
                ]
            },
        },
    )
    assert response.status_code == 422


def test_submit_story_rejects_unknown_context_fields(test_db, api_client):
    """POST /api/stories returns 422 for unknown fields in context (typo guard)."""
    response = api_client.post(
        "/api/stories",
        json={
            "story_text": "I had to restart the CI pipeline three times today because of flaky tests. " * 2,
            "signification": {"responses": []},
            "context": {"deparment": "engineering"},  # typo: 'deparment'
        },
    )
    assert response.status_code == 422
