"""Integration tests for insights API endpoint."""

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
    """TestClient with NoOp graph and LLM that returns a fixed synthesis."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import InsightContext, InsightOutput, SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpGraph(GraphPort):
        def save_story_node(self, story_id, triads, timestamp):
            pass

        def save_entity_nodes(self, story_id, entities):
            pass

        def save_theme_nodes(self, story_id, themes):
            pass

        def save_proximity_relationships(self, story_id, pairs):
            pass

        def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None):
            return []

        def count_stories_by_entity(self, entity_name):
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

        def find_story_communities(self, triad_id):
            return []


    class FixedInsightLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_themes(self, story_text: str) -> list:
            return []

        def extract_relationships(self, story_text: str) -> list:
            return []

        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

        def synthesize_insights(self, context: InsightContext) -> InsightOutput:
            return InsightOutput(narrative="Test insight narrative.", caveats=["Sample caveat."])

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: FixedInsightLLM()
    app.dependency_overrides[get_graph] = lambda: NoOpGraph()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


def test_synthesize_returns_empty_narrative_when_no_stories(test_db, api_client):
    """POST /api/insights/synthesize returns empty narrative when graph returns no stories."""
    response = api_client.post(
        "/api/insights/synthesize",
        json={"entity_name": "unknown entity", "query": "What patterns exist?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["narrative"] == ""
    assert body["story_count"] == 0


def test_synthesize_rejects_missing_entity_name(test_db, api_client):
    """POST /api/insights/synthesize returns 422 when entity_name is missing."""
    response = api_client.post(
        "/api/insights/synthesize",
        json={"query": "What patterns exist?"},
    )
    assert response.status_code == 422


def test_synthesize_rejects_missing_query(test_db, api_client):
    """POST /api/insights/synthesize returns 422 when query is missing."""
    response = api_client.post(
        "/api/insights/synthesize",
        json={"entity_name": "CI pipeline"},
    )
    assert response.status_code == 422


def test_synthesize_returns_narrative_when_stories_exist(test_db):
    """Narrative and evidence are returned when matching stories exist."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import InsightContext, InsightOutput, SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class FixedInsightLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_themes(self, story_text: str) -> list:
            return []

        def extract_relationships(self, story_text: str) -> list:
            return []

        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

        def synthesize_insights(self, context: InsightContext) -> InsightOutput:
            return InsightOutput(narrative="CI friction is high.", caveats=["Only sample."])

    story_ids = []

    class CapturingGraph(GraphPort):
        def save_story_node(self, story_id, triads, timestamp):
            story_ids.append(story_id)

        def save_entity_nodes(self, story_id, entities):
            pass

        def save_theme_nodes(self, story_id, themes):
            pass

        def save_proximity_relationships(self, story_id, pairs):
            pass

        def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None):
            return list(story_ids)

        def count_stories_by_entity(self, entity_name):
            return len(story_ids)

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

        def find_story_communities(self, triad_id):
            return []


    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: FixedInsightLLM()
    app.dependency_overrides[get_graph] = lambda: CapturingGraph()
    try:
        with TestClient(app) as client:
            # Submit a story
            resp = client.post(
                "/api/stories",
                json={
                    "story_text": "CI pipeline kept failing repeatedly and blocked our entire team. " * 2,
                    "triads": [
                        {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
                        {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
                        {"triad_id": "value_character", "x": 0.2, "y": 0.7},
                    ],
                },
            )
            assert resp.status_code == 201

            resp2 = client.post(
                "/api/insights/synthesize",
                json={"entity_name": "CI pipeline", "query": "Why do CI stories cluster here?"},
            )
            assert resp2.status_code == 200
            body = resp2.json()
            assert body["narrative"] == "CI friction is high."
            assert body["story_count"] == 1
            assert body["caveats"] == ["Only sample."]
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


def test_synthesize_rejects_blank_entity_name(test_db, api_client):
    """POST /api/insights/synthesize returns 422 when entity_name is blank."""
    response = api_client.post(
        "/api/insights/synthesize",
        json={"entity_name": "", "query": "What patterns exist?"},
    )
    assert response.status_code == 422


def test_synthesize_rejects_whitespace_entity_name(test_db, api_client):
    """POST /api/insights/synthesize returns 422 when entity_name is whitespace only."""
    response = api_client.post(
        "/api/insights/synthesize",
        json={"entity_name": "   ", "query": "What patterns exist?"},
    )
    assert response.status_code == 422


def test_synthesize_rejects_blank_query(test_db, api_client):
    """POST /api/insights/synthesize returns 422 when query is blank."""
    response = api_client.post(
        "/api/insights/synthesize",
        json={"entity_name": "CI pipeline", "query": ""},
    )
    assert response.status_code == 422


def test_synthesize_rejects_whitespace_query(test_db, api_client):
    """POST /api/insights/synthesize returns 422 when query is whitespace only."""
    response = api_client.post(
        "/api/insights/synthesize",
        json={"entity_name": "CI pipeline", "query": "   "},
    )
    assert response.status_code == 422


def test_synthesize_returns_503_on_storage_error(test_db):
    """StorageError during story hydration returns 503."""
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import InsightContext, InsightOutput, SentimentAnalysis, Story
    from src.ports.errors import StorageError
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort
    from src.ports.storage import StoragePort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_themes(self, story_text: str) -> list:
            return []

        def extract_relationships(self, story_text: str) -> list:
            return []

        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

        def synthesize_insights(self, context: InsightContext) -> InsightOutput:
            return InsightOutput(narrative="")

    class OneIdGraph(GraphPort):
        def save_story_node(self, story_id, triads, timestamp):
            pass

        def save_entity_nodes(self, story_id, entities):
            pass

        def save_theme_nodes(self, story_id, themes):
            pass

        def save_proximity_relationships(self, story_id, pairs):
            pass

        def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None):
            return ["missing-id"]

        def count_stories_by_entity(self, entity_name):
            return 1

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

        def find_story_communities(self, triad_id):
            return []


    class ErrorStorage(StoragePort):
        def save_story(self, story: Story) -> str:
            return story.id

        def get_story(self, story_id: str) -> Story:
            raise StorageError("Mongo down")

        def count_stories(self, from_date=None, to_date=None) -> int:
            return 0

        def list_stories(self, limit: int = 20, offset: int = 0, from_date=None, to_date=None) -> list:
            return []

        def update_story_entities(self, story_id, entities, themes, processing_status):
            pass

        def update_story_sentiment(self, story_id, sentiment, processing_status):
            pass

    app.dependency_overrides[get_storage] = lambda: ErrorStorage()
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: OneIdGraph()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/insights/synthesize",
                json={"entity_name": "CI", "query": "Test?"},
            )
            assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


def test_synthesize_returns_503_on_graph_error(test_db):
    """GraphError from the graph returns 503."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import InsightContext, InsightOutput, SentimentAnalysis
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
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

        def synthesize_insights(self, context: InsightContext) -> InsightOutput:
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

        def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None):
            raise GraphError("Neo4j down")

        def count_stories_by_entity(self, entity_name):
            raise GraphError("Neo4j down")

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

        def find_story_communities(self, triad_id):
            return []


    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: FailingGraph()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/insights/synthesize",
                json={"entity_name": "CI", "query": "Test?"},
            )
            assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)
