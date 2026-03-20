"""Tests for InsightSynthesisService."""

import pytest

from src.domain.models import (
    InsightContext,
    InsightOutput,
    SentimentAnalysis,
    Story,
    TriadCoordinates,
    TriadPlacement,
)
from src.ports.errors import LLMError, NotFoundError
from src.ports.graph import GraphPort
from src.ports.llm import EntityExtraction, LLMPort
from src.ports.storage import StoragePort

# ── Fakes ─────────────────────────────────────────────────────────────────────


def make_story(
    story_id: str = "s1",
    text: str = "CI failures blocked our deployment repeatedly this sprint again. " * 2,
    themes: list[str] | None = None,
    sentiment: SentimentAnalysis | None = None,
) -> Story:
    return Story(
        id=story_id,
        story_text=text,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
        processing_status="processed",
        themes=themes or [],
        sentiment=sentiment,
    )


class FakeGraph(GraphPort):
    def __init__(self, story_ids: list[str] | None = None, total: int = 0):
        self._story_ids = story_ids or []
        self._total = total

    def save_story_node(self, story_id, triads, timestamp):
        pass

    def save_entity_nodes(self, story_id, entities):
        pass

    def save_theme_nodes(self, story_id, themes):
        pass

    def save_proximity_relationships(self, story_id, pairs):
        pass

    def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int) -> list[str]:
        return list(self._story_ids[:limit])

    def count_stories_by_entity(self, entity_name: str) -> int:
        return self._total

    def find_themes_ranked(self, limit, from_date=None, to_date=None):
        return []

    def find_story_ids_by_theme(self, theme_name, limit, offset):
        return []

    def count_stories_by_theme(self, theme_name):
        return 0


class FakeStorage(StoragePort):
    def __init__(self, stories: dict | None = None):
        self._stories = stories or {}

    def save_story(self, story: Story) -> str:
        return story.id

    def get_story(self, story_id: str) -> Story:
        if story_id not in self._stories:
            raise NotFoundError(f"Story not found: {story_id}")
        return self._stories[story_id]

    def count_stories(self, from_date=None, to_date=None) -> int:
        return len(self._stories)

    def list_stories(self, limit: int = 20, offset: int = 0, from_date=None, to_date=None) -> list:
        return list(self._stories.values())[offset : offset + limit]

    def update_story_entities(self, story_id, entities, themes, processing_status):
        pass

    def update_story_sentiment(self, story_id, sentiment, processing_status):
        pass


class FakeLLM(LLMPort):
    def __init__(self, output: InsightOutput | None = None):
        self._output = output or InsightOutput(narrative="Patterns detected.", caveats=[])
        self.calls: list[InsightContext] = []

    def extract_entities(self, story_text: str) -> EntityExtraction:
        return EntityExtraction(entities=[])

    def extract_themes(self, story_text: str) -> list:
        return []

    def extract_relationships(self, story_text: str) -> list:
        return []

    def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
        return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

    def synthesize_insights(self, context: InsightContext) -> InsightOutput:
        self.calls.append(context)
        return self._output


class FailingLLM(FakeLLM):
    def synthesize_insights(self, context: InsightContext) -> InsightOutput:
        raise LLMError("LLM unavailable")


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_synthesize_returns_insight_response():
    """synthesize returns narrative and evidence from the LLM output."""
    from src.services.insight_synthesis import InsightSynthesisService

    story = make_story()
    graph = FakeGraph(story_ids=["s1"], total=1)
    storage = FakeStorage(stories={"s1": story})
    llm = FakeLLM(output=InsightOutput(narrative="CI friction is high.", caveats=["Only 1 story."]))

    service = InsightSynthesisService(graph=graph, storage=storage, llm=llm)
    result = service.synthesize(entity_name="CI pipeline", query="Why do CI stories cluster here?")

    assert result.narrative == "CI friction is high."
    assert result.caveats == ["Only 1 story."]
    assert result.story_count == 1


def test_synthesize_passes_query_and_entity_to_llm():
    """The InsightContext passed to the LLM contains the query and entity name."""
    from src.services.insight_synthesis import InsightSynthesisService

    story = make_story()
    graph = FakeGraph(story_ids=["s1"], total=1)
    storage = FakeStorage(stories={"s1": story})
    llm = FakeLLM()

    service = InsightSynthesisService(graph=graph, storage=storage, llm=llm)
    service.synthesize(entity_name="CI pipeline", query="What changed in Q2?")

    assert len(llm.calls) == 1
    ctx = llm.calls[0]
    assert ctx.query == "What changed in Q2?"
    assert ctx.entity_name == "CI pipeline"


def test_synthesize_computes_theme_counts():
    """Theme counts are computed from story themes before calling the LLM."""
    from src.services.insight_synthesis import InsightSynthesisService

    s1 = make_story("s1", themes=["automation friction", "developer experience"])
    s2 = make_story("s2", themes=["automation friction", "deployment pain"])
    graph = FakeGraph(story_ids=["s1", "s2"], total=2)
    storage = FakeStorage(stories={"s1": s1, "s2": s2})
    llm = FakeLLM()

    service = InsightSynthesisService(graph=graph, storage=storage, llm=llm)
    service.synthesize(entity_name="CI pipeline", query="Themes?")

    ctx = llm.calls[0]
    assert ctx.theme_counts["automation friction"] == 2
    assert ctx.theme_counts["developer experience"] == 1
    assert ctx.theme_counts["deployment pain"] == 1


def test_synthesize_computes_sentiment_summary():
    """Sentiment summary is computed from story sentiments before calling the LLM."""
    from src.services.insight_synthesis import InsightSynthesisService

    s1 = make_story("s1", sentiment=SentimentAnalysis(
        emotion_markers=[], process_sentiment="negative", outcome_sentiment="positive"
    ))
    s2 = make_story("s2", sentiment=SentimentAnalysis(
        emotion_markers=[], process_sentiment="negative", outcome_sentiment="neutral"
    ))
    s3 = make_story("s3")  # no sentiment

    graph = FakeGraph(story_ids=["s1", "s2", "s3"], total=3)
    storage = FakeStorage(stories={"s1": s1, "s2": s2, "s3": s3})
    llm = FakeLLM()

    service = InsightSynthesisService(graph=graph, storage=storage, llm=llm)
    service.synthesize(entity_name="CI", query="Sentiment?")

    ctx = llm.calls[0]
    assert ctx.sentiment_summary.negative_process == 2
    assert ctx.sentiment_summary.positive_outcome == 1
    assert ctx.sentiment_summary.neutral_outcome == 1


def test_synthesize_excerpts_truncated_to_300_chars():
    """Story text excerpts are capped at 300 characters."""
    from src.services.insight_synthesis import InsightSynthesisService

    long_text = "A" * 500 + " and more words to fill this out past 500 characters total."
    story = make_story("s1", text=long_text[:2000])
    graph = FakeGraph(story_ids=["s1"], total=1)
    storage = FakeStorage(stories={"s1": story})
    llm = FakeLLM()

    service = InsightSynthesisService(graph=graph, storage=storage, llm=llm)
    service.synthesize(entity_name="A", query="Test?")

    ctx = llm.calls[0]
    assert len(ctx.excerpts[0].text_excerpt) <= 300


def test_synthesize_caps_at_20_stories():
    """At most 20 story excerpts are passed to the LLM regardless of total."""
    from src.services.insight_synthesis import InsightSynthesisService

    stories = {f"s{i}": make_story(f"s{i}") for i in range(25)}
    ids = list(stories.keys())
    graph = FakeGraph(story_ids=ids, total=25)
    storage = FakeStorage(stories=stories)
    llm = FakeLLM()

    service = InsightSynthesisService(graph=graph, storage=storage, llm=llm)
    service.synthesize(entity_name="CI", query="Test?")

    ctx = llm.calls[0]
    assert len(ctx.excerpts) <= 20


def test_synthesize_total_stories_is_full_count():
    """total_stories in context reflects the full graph count, not just the sample."""
    from src.services.insight_synthesis import InsightSynthesisService

    stories = {f"s{i}": make_story(f"s{i}") for i in range(5)}
    graph = FakeGraph(story_ids=list(stories.keys()), total=42)
    storage = FakeStorage(stories=stories)
    llm = FakeLLM()

    service = InsightSynthesisService(graph=graph, storage=storage, llm=llm)
    service.synthesize(entity_name="CI", query="Test?")

    ctx = llm.calls[0]
    assert ctx.total_stories == 42


def test_synthesize_includes_triad_positions_in_excerpts():
    """Excerpt triad positions reflect the story's actual triad placements."""
    from src.services.insight_synthesis import InsightSynthesisService

    story = make_story("s1")
    graph = FakeGraph(story_ids=["s1"], total=1)
    storage = FakeStorage(stories={"s1": story})
    llm = FakeLLM()

    service = InsightSynthesisService(graph=graph, storage=storage, llm=llm)
    service.synthesize(entity_name="CI", query="Test?")

    ctx = llm.calls[0]
    positions = ctx.excerpts[0].triad_positions
    assert "workflow_nature" in positions
    assert positions["workflow_nature"] == {"x": 0.3, "y": 0.6}


def test_synthesize_propagates_llm_error():
    """LLMError from the LLM is not swallowed."""
    from src.services.insight_synthesis import InsightSynthesisService

    story = make_story()
    graph = FakeGraph(story_ids=["s1"], total=1)
    storage = FakeStorage(stories={"s1": story})

    service = InsightSynthesisService(graph=graph, storage=storage, llm=FailingLLM())
    with pytest.raises(LLMError):
        service.synthesize(entity_name="CI", query="Test?")


def test_synthesize_empty_result_when_no_stories():
    """Returns empty narrative with zero count when no stories match."""
    from src.services.insight_synthesis import InsightSynthesisService

    graph = FakeGraph(story_ids=[], total=0)
    storage = FakeStorage(stories={})
    llm = FakeLLM()

    service = InsightSynthesisService(graph=graph, storage=storage, llm=llm)
    result = service.synthesize(entity_name="unknown", query="Test?")

    assert result.story_count == 0
    assert result.narrative == ""
    assert llm.calls == []  # LLM not called when no stories


def test_synthesize_unknown_sentiment_labels_not_counted_as_neutral():
    """Sentiment values other than positive/negative/neutral are not bucketed into neutral."""
    from src.services.insight_synthesis import InsightSynthesisService

    s1 = make_story("s1", sentiment=SentimentAnalysis(
        emotion_markers=[], process_sentiment="mixed", outcome_sentiment="ambivalent"
    ))
    graph = FakeGraph(story_ids=["s1"], total=1)
    storage = FakeStorage(stories={"s1": s1})
    llm = FakeLLM()

    service = InsightSynthesisService(graph=graph, storage=storage, llm=llm)
    service.synthesize(entity_name="CI", query="Test?")

    ctx = llm.calls[0]
    s = ctx.sentiment_summary
    assert s.neutral_process == 0
    assert s.neutral_outcome == 0
    assert s.positive_process == 0
    assert s.negative_process == 0
