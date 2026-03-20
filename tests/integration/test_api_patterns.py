"""Integration tests for patterns API endpoint."""

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
    """TestClient with MongoDB storage and a capturing graph for entity queries."""
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
            return SentimentAnalysis(
                emotion_markers=[],
                process_sentiment="neutral",
                outcome_sentiment="neutral",
            )

        def synthesize_insights(self, context):  # type: ignore[override]
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")

    class NoOpGraph(GraphPort):
        def save_story_node(self, story_id: str, triads, timestamp: str) -> None:
            pass

        def save_entity_nodes(self, story_id: str, entities: list) -> None:
            pass

        def save_theme_nodes(self, story_id: str, themes: list) -> None:
            pass

        def save_proximity_relationships(self, story_id: str, pairs: list) -> None:
            pass

        def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int) -> list:
            return []

        def count_stories_by_entity(self, entity_name: str) -> int:
            return 0

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


def test_query_by_entity_returns_200(test_db, api_client):
    """GET /api/patterns/by-entity/{name} returns 200 and empty list when no matches."""
    response = api_client.get("/api/patterns/by-entity/SomeEntity")
    assert response.status_code == 200
    body = response.json()
    assert body["stories"] == []
    assert body["total"] == 0
    assert body["limit"] == 20
    assert body["offset"] == 0


def test_query_by_entity_pagination_params(test_db, api_client):
    """Pagination params are reflected in the response."""
    response = api_client.get("/api/patterns/by-entity/Entity?limit=5&offset=10")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 5
    assert body["offset"] == 10


def test_query_by_entity_rejects_invalid_pagination(test_db, api_client):
    """Invalid pagination params return 422."""
    assert api_client.get("/api/patterns/by-entity/Entity?limit=0").status_code == 422
    assert api_client.get("/api/patterns/by-entity/Entity?limit=101").status_code == 422
    assert api_client.get("/api/patterns/by-entity/Entity?offset=-1").status_code == 422


def test_query_by_entity_returns_503_on_graph_error(test_db):
    """GraphError from the graph adapter returns 503."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.errors import GraphError
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
            return SentimentAnalysis(
                emotion_markers=[],
                process_sentiment="neutral",
                outcome_sentiment="neutral",
            )

        def synthesize_insights(self, context):  # type: ignore[override]
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")

    class FailingGraph(GraphPort):
        def save_story_node(self, story_id, triads, timestamp):
            pass

        def save_entity_nodes(self, story_id, entities):
            pass

        def save_theme_nodes(self, story_id, themes):
            pass

        def save_proximity_relationships(self, story_id, pairs):
            pass

        def find_story_ids_by_entity(self, entity_name, limit, offset):
            raise GraphError("Neo4j unavailable")

        def count_stories_by_entity(self, entity_name):
            raise GraphError("Neo4j unavailable")

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: FailingGraph()
    try:
        with TestClient(app) as client:
            response = client.get("/api/patterns/by-entity/SomeEntity")
            assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


def test_query_by_entity_returns_stories_from_graph(test_db):
    """Stories whose IDs are returned by the graph are loaded from storage."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    # Submit a story first so it exists in MongoDB
    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_themes(self, story_text: str) -> list:
            return []

        def extract_relationships(self, story_text: str) -> list:
            return []

        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            return SentimentAnalysis(
                emotion_markers=[],
                process_sentiment="neutral",
                outcome_sentiment="neutral",
            )

        def synthesize_insights(self, context):  # type: ignore[override]
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")

    story_ids = []

    class CapturingGraph(GraphPort):
        def save_story_node(self, story_id: str, triads, timestamp: str) -> None:
            story_ids.append(story_id)

        def save_entity_nodes(self, story_id: str, entities: list) -> None:
            pass

        def save_theme_nodes(self, story_id: str, themes: list) -> None:
            pass

        def save_proximity_relationships(self, story_id: str, pairs: list) -> None:
            pass

        def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int) -> list:
            return list(story_ids)

        def count_stories_by_entity(self, entity_name: str) -> int:
            return len(story_ids)

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: CapturingGraph()
    try:
        with TestClient(app) as client:
            # Submit a story
            resp = client.post(
                "/api/stories",
                json={
                    "story_text": "CI failures blocked deployment repeatedly this sprint and last. " * 2,
                    "triads": [
                        {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
                        {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
                        {"triad_id": "value_character", "x": 0.2, "y": 0.7},
                    ],
                },
            )
            assert resp.status_code == 201

            # Query by entity — graph returns the saved story_id
            resp2 = client.get("/api/patterns/by-entity/CI")
            assert resp2.status_code == 200
            body = resp2.json()
            assert body["total"] == 1
            assert len(body["stories"]) == 1
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)
