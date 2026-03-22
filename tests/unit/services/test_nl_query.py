"""Tests for NLQueryService — natural language question → graph query → synthesized answer."""

from datetime import datetime, UTC

import pytest

from src.domain.models import (
    InsightContext,
    InsightOutput,
    QueryIntent,
    SentimentAnalysis,
    Story,
    StoryMetadata,
    TriadCoordinates,
    TriadPlacement,
)
from src.ports.errors import GraphError, LLMError, QueryTranslationError
from src.ports.graph import GraphPort
from src.ports.llm import EntityExtraction, LLMPort
from src.ports.storage import StoragePort


# ── Fakes ─────────────────────────────────────────────────────────────────────


def make_story(story_id: str) -> Story:
    return Story(
        id=story_id,
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.5)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
        processing_status="processed",
        timestamp=datetime(2026, 1, 15, tzinfo=UTC),
        themes=["automation friction"],
        entities=[{"name": "CI pipeline", "type": "tool"}],
    )


class FakeGraph(GraphPort):
    def __init__(self, entity_ids=None, theme_ids=None, entity_count=0, theme_count=0):
        self._entity_ids = entity_ids or []
        self._theme_ids = theme_ids or []
        self._entity_count = entity_count
        self._theme_count = theme_count

    def save_story_node(self, story_id, triads, timestamp): pass
    def save_entity_nodes(self, story_id, entities): pass
    def save_theme_nodes(self, story_id, themes): pass
    def save_proximity_relationships(self, story_id, pairs): pass
    def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None):
        return self._entity_ids[offset:offset + limit]
    def count_stories_by_entity(self, entity_name): return self._entity_count
    def find_themes_ranked(self, limit, from_date=None, to_date=None): return []
    def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None):
        return self._theme_ids[offset:offset + limit]
    def count_stories_by_theme(self, theme_name): return self._theme_count
    def find_entity_correlations(self, limit, threshold=0.0, entity_type=None): return []
    def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0): return []
    def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
    def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []
    def find_story_communities(self, triad_id): return []


class FakeStorage(StoragePort):
    def __init__(self, stories=None):
        self._stories = stories or {}

    def save_story(self, story): return story.id
    def get_story(self, story_id): return self._stories[story_id]
    def count_stories(self, from_date=None, to_date=None): return len(self._stories)
    def list_stories(self, limit=20, offset=0, from_date=None, to_date=None):
        return list(self._stories.values())[offset:offset + limit]
    def update_story_entities(self, story_id, entities, themes, processing_status): pass
    def update_story_sentiment(self, story_id, sentiment, processing_status): pass


class FakeLLM(LLMPort):
    """Configurable fake LLM for NL query tests."""

    def __init__(self, intent: QueryIntent, narrative: str = "Synthesized answer."):
        self._intent = intent
        self._narrative = narrative
        self.translate_calls: list[str] = []

    def extract_entities(self, story_text): return EntityExtraction(entities=[])
    def extract_themes(self, story_text): return []
    def extract_relationships(self, story_text): return []
    def extract_sentiment(self, story_text):
        return SentimentAnalysis(
            emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral"
        )
    def synthesize_insights(self, context: InsightContext) -> InsightOutput:
        return InsightOutput(narrative=self._narrative)
    def translate_query(self, question: str) -> QueryIntent:
        self.translate_calls.append(question)
        return self._intent


class FailingTranslateLLM(FakeLLM):
    def translate_query(self, question: str) -> QueryIntent:
        raise LLMError("LLM down")


# ── Test 1: entity intent → stories fetched by entity → synthesized ──────────


def test_nl_query_entity_intent_fetches_by_entity_and_synthesizes():
    """When LLM returns entity intent, service fetches stories by entity and synthesizes."""
    from src.services.nl_query import NLQueryService

    s1 = make_story("s1")
    intent = QueryIntent(operation="by_entity", entity="CI pipeline")
    llm = FakeLLM(intent=intent, narrative="CI pipeline causes friction.")
    graph = FakeGraph(entity_ids=["s1"], entity_count=1)
    storage = FakeStorage(stories={"s1": s1})

    service = NLQueryService(graph=graph, storage=storage, llm=llm)
    result = service.query("What issues exist with the CI pipeline?")

    assert result.answer == "CI pipeline causes friction."
    assert result.story_count == 1


# ── Test 2: theme intent → stories fetched by theme → synthesized ─────────────


def test_nl_query_theme_intent_fetches_by_theme_and_synthesizes():
    """When LLM returns theme intent, service fetches stories by theme and synthesizes."""
    from src.services.nl_query import NLQueryService

    s1 = make_story("s1")
    intent = QueryIntent(operation="by_theme", theme="automation friction")
    llm = FakeLLM(intent=intent, narrative="Automation friction is common.")
    graph = FakeGraph(theme_ids=["s1"], theme_count=1)
    storage = FakeStorage(stories={"s1": s1})

    service = NLQueryService(graph=graph, storage=storage, llm=llm)
    result = service.query("Tell me about automation friction themes.")

    assert result.answer == "Automation friction is common."
    assert result.story_count == 1


# ── Test 3: unknown intent → QueryTranslationError ────────────────────────────


def test_nl_query_unknown_intent_raises_translation_error():
    """When LLM returns unknown operation, service raises QueryTranslationError."""
    from src.services.nl_query import NLQueryService

    intent = QueryIntent(operation="unknown", explanation="Could not determine query type.")
    llm = FakeLLM(intent=intent)
    service = NLQueryService(graph=FakeGraph(), storage=FakeStorage(), llm=llm)

    with pytest.raises(QueryTranslationError) as exc_info:
        service.query("What is the meaning of life?")

    assert "Could not determine query type." in str(exc_info.value)


# ── Test 4: LLMError from translate_query propagates ─────────────────────────


def test_nl_query_llm_error_from_translation_propagates():
    """LLMError raised during translation propagates to the caller."""
    from src.services.nl_query import NLQueryService

    intent = QueryIntent(operation="by_entity", entity="anything")
    llm = FailingTranslateLLM(intent=intent)
    service = NLQueryService(graph=FakeGraph(), storage=FakeStorage(), llm=llm)

    with pytest.raises(LLMError):
        service.query("Any question")


# ── Test 5: question forwarded to translate_query ────────────────────────────


def test_nl_query_forwards_question_to_llm():
    """The original question string is passed to llm.translate_query."""
    from src.services.nl_query import NLQueryService

    intent = QueryIntent(operation="by_entity", entity="CI pipeline")
    llm = FakeLLM(intent=intent)
    graph = FakeGraph(entity_ids=["s1"], entity_count=1)
    storage = FakeStorage(stories={"s1": make_story("s1")})
    service = NLQueryService(graph=graph, storage=storage, llm=llm)

    service.query("Which tools frustrate developers?")

    assert llm.translate_calls == ["Which tools frustrate developers?"]


# ── Test 6: no stories for entity → empty answer ─────────────────────────────


def test_nl_query_no_matching_stories_returns_empty_answer():
    """When no stories match the intent, answer is empty and story_count is 0."""
    from src.services.nl_query import NLQueryService

    intent = QueryIntent(operation="by_entity", entity="unknown tool")
    llm = FakeLLM(intent=intent)
    graph = FakeGraph(entity_ids=[], entity_count=0)
    service = NLQueryService(graph=graph, storage=FakeStorage(), llm=llm)

    result = service.query("What about unknown tool?")

    assert result.answer == ""
    assert result.story_count == 0


# ── Test 7: GraphError propagates ────────────────────────────────────────────


def test_nl_query_graph_error_propagates():
    """GraphError from graph operations propagates to the caller."""
    from src.services.nl_query import NLQueryService

    class FailingGraph(FakeGraph):
        def count_stories_by_entity(self, entity_name):
            raise GraphError("graph down")

    intent = QueryIntent(operation="by_entity", entity="CI pipeline")
    llm = FakeLLM(intent=intent)
    service = NLQueryService(graph=FailingGraph(), storage=FakeStorage(), llm=llm)

    with pytest.raises(GraphError):
        service.query("Any question")
