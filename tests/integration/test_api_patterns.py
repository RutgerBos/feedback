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
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


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
            raise GraphError("Neo4j unavailable")

        def count_stories_by_entity(self, entity_name):
            raise GraphError("Neo4j unavailable")

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
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


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

        def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int, from_date=None, to_date=None) -> list:
            return list(story_ids)

        def count_stories_by_entity(self, entity_name: str) -> int:
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
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []

        def find_story_communities(self, triad_id):
            return []


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
                    "signification": {"responses": [
                        {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
                        {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
                        {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.2, "y": 0.7}},
                    ]},
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


def test_get_themes_returns_200_with_empty_list(test_db, api_client):
    """GET /api/patterns/themes returns 200 and empty list when no themes."""
    response = api_client.get("/api/patterns/themes")
    assert response.status_code == 200
    body = response.json()
    assert body["themes"] == []


def test_get_themes_returns_503_on_graph_error(test_db):
    """GraphError from graph adapter returns 503."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.errors import GraphError
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context):
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


    class FailingThemesGraph(GraphPort):
        def save_story_node(self, story_id, triads, timestamp): pass
        def save_entity_nodes(self, story_id, entities): pass
        def save_theme_nodes(self, story_id, themes): pass
        def save_proximity_relationships(self, story_id, pairs): pass
        def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None): return []
        def count_stories_by_entity(self, entity_name): return 0
        def find_themes_ranked(self, limit, from_date=None, to_date=None):
            raise GraphError("Neo4j unavailable")
        def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None): return []
        def count_stories_by_theme(self, theme_name): return 0
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
    app.dependency_overrides[get_graph] = lambda: FailingThemesGraph()
    try:
        with TestClient(app) as client:
            response = client.get("/api/patterns/themes")
            assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


def test_get_themes_returns_ranked_themes_with_sample_ids(test_db):
    """GET /api/patterns/themes returns themes with story_count and sample_story_ids."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context):
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


    class ThemeGraph(GraphPort):
        def save_story_node(self, story_id, triads, timestamp): pass
        def save_entity_nodes(self, story_id, entities): pass
        def save_theme_nodes(self, story_id, themes): pass
        def save_proximity_relationships(self, story_id, pairs): pass
        def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None): return []
        def count_stories_by_entity(self, entity_name): return 0
        def find_themes_ranked(self, limit, from_date=None, to_date=None):
            return [("automation friction", 5), ("tooling", 2)]
        def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None):
            return ["story-1", "story-2"][:limit]
        def count_stories_by_theme(self, theme_name): return 0
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
    app.dependency_overrides[get_graph] = lambda: ThemeGraph()
    try:
        with TestClient(app) as client:
            response = client.get("/api/patterns/themes")
            assert response.status_code == 200
            body = response.json()
            assert len(body["themes"]) == 2
            assert body["themes"][0]["name"] == "automation friction"
            assert body["themes"][0]["story_count"] == 5
            assert "sample_story_ids" in body["themes"][0]
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


# ── Story 4.3: GET /api/patterns/correlations ─────────────────────────────────


def test_get_correlations_returns_200_with_empty_list(test_db, api_client):
    """GET /api/patterns/correlations returns 200 and empty pairs when no correlations."""
    response = api_client.get("/api/patterns/correlations")
    assert response.status_code == 200
    assert response.json() == {"pairs": []}


def test_get_correlations_returns_503_on_graph_error(test_db):
    """GET /api/patterns/correlations returns 503 when graph is unavailable."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.errors import GraphError
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context):
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


    class FailingGraph(GraphPort):
        def save_story_node(self, story_id, triads, timestamp): pass
        def save_entity_nodes(self, story_id, entities): pass
        def save_theme_nodes(self, story_id, themes): pass
        def save_proximity_relationships(self, story_id, pairs): pass
        def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None): return []
        def count_stories_by_entity(self, entity_name): return 0
        def find_themes_ranked(self, limit, from_date=None, to_date=None): return []
        def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None): return []
        def count_stories_by_theme(self, theme_name): return 0
        def find_entity_correlations(self, limit, threshold=0.0, entity_type=None):
            raise GraphError("Neo4j down")
        def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0): return []
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []
        def find_story_communities(self, triad_id): return []

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: FailingGraph()
    try:
        with TestClient(app) as client:
            response = client.get("/api/patterns/correlations")
            assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


def test_get_correlations_returns_ranked_pairs_with_sample_ids(test_db):
    """GET /api/patterns/correlations returns pairs with jaccard and sample story IDs."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context):
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


    class CorrelationGraph(GraphPort):
        def save_story_node(self, story_id, triads, timestamp): pass
        def save_entity_nodes(self, story_id, entities): pass
        def save_theme_nodes(self, story_id, themes): pass
        def save_proximity_relationships(self, story_id, pairs): pass
        def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None): return []
        def count_stories_by_entity(self, entity_name): return 0
        def find_themes_ranked(self, limit, from_date=None, to_date=None): return []
        def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None): return []
        def count_stories_by_theme(self, theme_name): return 0
        def find_entity_correlations(self, limit, threshold=0.0, entity_type=None):
            return [("CI pipeline", "deployment", 5, 0.71)]
        def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0):
            return ["story-1"]
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []
        def find_story_communities(self, triad_id): return []

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: CorrelationGraph()
    try:
        with TestClient(app) as client:
            response = client.get("/api/patterns/correlations")
            assert response.status_code == 200
            body = response.json()
            assert len(body["pairs"]) == 1
            pair = body["pairs"][0]
            assert pair["entity_a"] == "CI pipeline"
            assert pair["entity_b"] == "deployment"
            assert pair["co_count"] == 5
            assert pair["jaccard"] == 0.71
            assert pair["sample_story_ids"] == ["story-1"]
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


# ── Story 4.4: GET /api/patterns/clusters ─────────────────────────────────────


def test_get_clusters_returns_200_with_empty_list(test_db, api_client):
    """GET /api/patterns/clusters returns 200 and empty clusters list when no proximity data."""
    response = api_client.get("/api/patterns/clusters?triad_id=workflow_nature")
    assert response.status_code == 200
    assert response.json() == {"clusters": []}


def test_get_clusters_returns_503_on_graph_error(test_db):
    """GET /api/patterns/clusters returns 503 when GDS is unavailable."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.errors import GraphError
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context):
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


    class FailingGraph(GraphPort):
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
        def find_story_communities(self, triad_id): raise GraphError("GDS down")

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: FailingGraph()
    try:
        with TestClient(app) as client:
            response = client.get("/api/patterns/clusters?triad_id=workflow_nature")
            assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


def test_get_clusters_returns_cluster_data(test_db):
    """GET /api/patterns/clusters returns clusters with story_ids, center, themes, entities."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis, Story, TriadCoordinates, TriadPlacement
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context):
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


    story = Story(
        id="s1",
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
        processing_status="processed",
        themes=["automation friction"],
        entities=[{"name": "CI pipeline", "type": "tool"}],
    )
    test_db.stories.insert_one({
        "_id": "s1", "story_text": story.story_text,
        "schema_version": 2,
        "triads": [],
        "signification": {"headline": None, "responses": [
            {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
            {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
            {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.2, "y": 0.7}},
        ]},
        "processing_status": "processed",
        "themes": story.themes, "entities": story.entities,
        "timestamp": "2026-03-20T10:00:00",
    })

    class ClusterGraph(GraphPort):
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
        def find_story_communities(self, triad_id): return [("s1", 0)]

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: ClusterGraph()
    try:
        with TestClient(app) as client:
            response = client.get("/api/patterns/clusters?triad_id=workflow_nature")
            assert response.status_code == 200
            body = response.json()
            assert len(body["clusters"]) == 1
            cluster = body["clusters"][0]
            assert "s1" in cluster["story_ids"]
            assert "center_x" in cluster
            assert "center_y" in cluster
            assert "top_themes" in cluster
            assert "top_entities" in cluster
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


# ── Story 4.5: GET /api/patterns/temporal ─────────────────────────────────────


def test_get_temporal_returns_200_with_empty_result(test_db, api_client):
    """GET /api/patterns/temporal returns 200 and empty lists when no data."""
    response = api_client.get("/api/patterns/temporal")
    assert response.status_code == 200
    body = response.json()
    assert "windows" in body
    assert "theme_frequency" in body
    assert "entity_frequency" in body
    assert "triad_drift" in body
    assert body["theme_frequency"] == []
    assert body["entity_frequency"] == []
    assert body["triad_drift"] == []


def test_get_temporal_returns_503_on_graph_error(test_db):
    """GET /api/patterns/temporal returns 503 when graph is unavailable."""
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.errors import GraphError
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context):
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


    class FailingGraph(GraphPort):
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
        def find_story_communities(self, triad_id): return []
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None):
            raise GraphError("graph down")
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: FailingGraph()
    try:
        with TestClient(app) as client:
            response = client.get("/api/patterns/temporal")
            assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


def test_get_temporal_returns_theme_and_drift_data(test_db):
    """GET /api/patterns/temporal returns theme timelines and triad drift from storage."""
    from datetime import datetime, UTC
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context):
            from src.domain.models import InsightOutput
            return InsightOutput(narrative="")
        def translate_query(self, question):  # type: ignore[override]
            from src.domain.models import QueryIntent
            return QueryIntent(operation="unknown")


    class TemporalGraph(GraphPort):
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
        def find_story_communities(self, triad_id): return []
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None):
            return [("2026-01", "automation friction", 2)]
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None):
            return [("2026-01", "CI pipeline", 1)]

    # Insert a story into MongoDB so drift can be computed
    test_db.stories.insert_one({
        "_id": "s1",
        "story_text": "CI failures blocked our deployment repeatedly this sprint. " * 3,
        "schema_version": 2,
        "triads": [],
        "signification": {"headline": None, "responses": [
            {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
            {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
            {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.2, "y": 0.7}},
        ]},
        "processing_status": "processed",
        "themes": ["automation friction"],
        "entities": [{"name": "CI pipeline", "type": "tool"}],
        "timestamp": datetime(2026, 1, 15, 10, 0, tzinfo=UTC).replace(tzinfo=None),
    })

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: TemporalGraph()
    try:
        with TestClient(app) as client:
            response = client.get("/api/patterns/temporal")
            assert response.status_code == 200
            body = response.json()
            assert len(body["theme_frequency"]) == 1
            assert body["theme_frequency"][0]["theme"] == "automation friction"
            assert len(body["entity_frequency"]) == 1
            assert body["entity_frequency"][0]["entity"] == "CI pipeline"
            assert len(body["triad_drift"]) > 0
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)


def test_get_temporal_department_filter_restricts_drift(test_db):
    """GET /api/patterns/temporal?department=... filters drift to matching stories."""
    from datetime import datetime, UTC
    from src.adapters.mongodb_storage import MongoDBStorageAdapter
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort

    class NoOpLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context):
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
        def find_story_communities(self, triad_id): return []
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []

    signification_doc = {"headline": None, "responses": [
        {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
        {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
        {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.2, "y": 0.7}},
    ]}
    # s1: engineering dept, developer role → Jan
    test_db.stories.insert_one({
        "_id": "s1",
        "story_text": "CI failures blocked our deployment repeatedly this sprint. " * 3,
        "schema_version": 2,
        "triads": [],
        "signification": signification_doc,
        "processing_status": "processed",
        "themes": [],
        "entities": [],
        "timestamp": datetime(2026, 1, 15, 10, 0, tzinfo=UTC).replace(tzinfo=None),
        "context": {"department": "engineering", "role": "developer", "tool_context": None},
    })
    # s2: product dept, manager role → Feb
    test_db.stories.insert_one({
        "_id": "s2",
        "story_text": "CI failures blocked our deployment repeatedly this sprint. " * 3,
        "schema_version": 2,
        "triads": [],
        "signification": signification_doc,
        "processing_status": "processed",
        "themes": [],
        "entities": [],
        "timestamp": datetime(2026, 2, 10, 10, 0, tzinfo=UTC).replace(tzinfo=None),
        "context": {"department": "product", "role": "manager", "tool_context": None},
    })

    app.dependency_overrides[get_storage] = lambda: MongoDBStorageAdapter(test_db)
    app.dependency_overrides[get_llm] = lambda: NoOpLLM()
    app.dependency_overrides[get_graph] = lambda: NoOpGraph()
    try:
        with TestClient(app) as client:
            # Without filter: both stories contribute → drift has 2 windows
            response_all = client.get("/api/patterns/temporal")
            assert response_all.status_code == 200
            all_drift = response_all.json()["triad_drift"]
            wf_all = next((d for d in all_drift if d["triad_id"] == "workflow_nature"), None)
            assert wf_all is not None
            assert len(wf_all["centroids"]) == 2

            # With department=engineering: only s1 contributes → drift has 1 window (Jan)
            response_eng = client.get("/api/patterns/temporal?department=engineering")
            assert response_eng.status_code == 200
            eng_drift = response_eng.json()["triad_drift"]
            wf_eng = next((d for d in eng_drift if d["triad_id"] == "workflow_nature"), None)
            assert wf_eng is not None
            assert len(wf_eng["centroids"]) == 1
            assert wf_eng["centroids"][0]["window"] == "2026-01"

            # With role=manager: only s2 contributes → drift has 1 window (Feb)
            response_mgr = client.get("/api/patterns/temporal?role=manager")
            assert response_mgr.status_code == 200
            mgr_drift = response_mgr.json()["triad_drift"]
            wf_mgr = next((d for d in mgr_drift if d["triad_id"] == "workflow_nature"), None)
            assert wf_mgr is not None
            assert len(wf_mgr["centroids"]) == 1
            assert wf_mgr["centroids"][0]["window"] == "2026-02"
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_graph, None)
