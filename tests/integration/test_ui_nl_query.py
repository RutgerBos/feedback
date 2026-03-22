"""Integration tests for the natural language query UI."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def nl_query_client():
    """TestClient with NLQueryService dependencies overridden."""
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import InsightOutput, QueryIntent, SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort
    from src.ports.storage import StoragePort

    class NoOpStorage(StoragePort):
        def save_story(self, story): return story.id
        def get_story(self, story_id): raise KeyError(story_id)
        def count_stories(self, from_date=None, to_date=None): return 0
        def list_stories(self, limit=20, offset=0, from_date=None, to_date=None): return []
        def update_story_entities(self, story_id, entities, themes, processing_status): pass
        def update_story_sentiment(self, story_id, sentiment, processing_status): pass

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

    class AnsweringLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context): return InsightOutput(narrative="")
        def translate_query(self, question):
            return QueryIntent(operation="by_entity", entity="CI pipeline")

    app.dependency_overrides[get_storage] = lambda: NoOpStorage()
    app.dependency_overrides[get_graph] = lambda: NoOpGraph()
    app.dependency_overrides[get_llm] = lambda: AnsweringLLM()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_graph, None)
        app.dependency_overrides.pop(get_llm, None)


# ── Test 1: GET /query returns the chat page ──────────────────────────────────


def test_query_page_returns_200(nl_query_client):
    """GET /query returns 200 HTML page."""
    response = nl_query_client.get("/query")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_query_page_has_question_input(nl_query_client):
    """GET /query page contains an input field for questions."""
    response = nl_query_client.get("/query")
    assert "question" in response.text


def test_query_page_has_conversation_history_area(nl_query_client):
    """GET /query page contains an area to display conversation history."""
    response = nl_query_client.get("/query")
    assert "conversation" in response.text.lower() or "history" in response.text.lower()


# ── Test 2: POST /ui/query with valid question returns answer fragment ─────────


def test_ui_query_valid_question_returns_answer_fragment(nl_query_client):
    """POST /ui/query with valid question returns HTML fragment with answer."""
    response = nl_query_client.post(
        "/ui/query",
        data={"question": "What issues exist with the CI pipeline?"},
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_ui_query_fragment_contains_question_echo(nl_query_client):
    """Response fragment echoes the user's question back."""
    response = nl_query_client.post(
        "/ui/query",
        data={"question": "What issues exist with the CI pipeline?"},
    )
    assert "What issues exist with the CI pipeline?" in response.text


# ── Test 3: POST /ui/query with blank question returns 400 fragment ───────────


def test_ui_query_blank_question_returns_400(nl_query_client):
    """POST /ui/query with blank question returns 400 error fragment."""
    response = nl_query_client.post("/ui/query", data={"question": "   "})
    assert response.status_code == 400
    assert "text/html" in response.headers["content-type"]


# ── Test 4: POST /ui/query on untranslatable question returns error fragment ──


def test_ui_query_untranslatable_question_returns_error_fragment():
    """POST /ui/query when LLM returns unknown intent returns an error fragment."""
    from src.api.main import app
    from src.api.stories import get_graph, get_llm, get_storage
    from src.domain.models import InsightOutput, QueryIntent, SentimentAnalysis
    from src.ports.graph import GraphPort
    from src.ports.llm import EntityExtraction, LLMPort
    from src.ports.storage import StoragePort

    class NoOpStorage(StoragePort):
        def save_story(self, story): return story.id
        def get_story(self, story_id): raise KeyError(story_id)
        def count_stories(self, from_date=None, to_date=None): return 0
        def list_stories(self, limit=20, offset=0, from_date=None, to_date=None): return []
        def update_story_entities(self, story_id, entities, themes, processing_status): pass
        def update_story_sentiment(self, story_id, sentiment, processing_status): pass

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

    class UnknownLLM(LLMPort):
        def extract_entities(self, story_text): return EntityExtraction(entities=[])
        def extract_themes(self, story_text): return []
        def extract_relationships(self, story_text): return []
        def extract_sentiment(self, story_text):
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")
        def synthesize_insights(self, context): return InsightOutput(narrative="")
        def translate_query(self, question):
            return QueryIntent(operation="unknown", explanation="Cannot determine query type.")

    app.dependency_overrides[get_storage] = lambda: NoOpStorage()
    app.dependency_overrides[get_graph] = lambda: NoOpGraph()
    app.dependency_overrides[get_llm] = lambda: UnknownLLM()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/ui/query",
                data={"question": "What is the meaning of life?"},
            )
            assert response.status_code == 400
            assert "text/html" in response.headers["content-type"]
    finally:
        app.dependency_overrides.pop(get_storage, None)
        app.dependency_overrides.pop(get_graph, None)
        app.dependency_overrides.pop(get_llm, None)
