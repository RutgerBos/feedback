"""Tests for EntityExtractionService."""

import pytest

from src.domain.models import SentimentAnalysis, Story, TriadCoordinates, TriadPlacement
from src.ports.errors import LLMError, NotFoundError
from src.ports.llm import EntityExtraction, LLMPort
from src.ports.storage import StoragePort


def make_story(story_id: str = "story-1") -> Story:
    """Build a minimal valid Story for testing."""
    return Story(
        id=story_id,
        story_text="I had to restart the CI pipeline three times today due to flaky tests. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
    )


class FakeStorage(StoragePort):
    """In-memory storage fake for unit tests."""

    def __init__(self, stories: dict = None):
        self.stories = stories or {}
        self.updated = {}  # story_id -> (entities, themes, status)

    def save_story(self, story: Story) -> str:
        self.stories[story.id] = story
        return story.id

    def get_story(self, story_id: str) -> Story:
        if story_id not in self.stories:
            raise NotFoundError(f"Story not found: {story_id}")
        return self.stories[story_id]

    def count_stories(self, from_date=None, to_date=None) -> int:
        return len(self.stories)

    def list_stories(self, limit: int = 20, offset: int = 0, from_date=None, to_date=None) -> list:
        return list(self.stories.values())[offset:offset + limit]

    def update_story_entities(self, story_id: str, entities: list, themes: list, processing_status: str) -> None:
        if story_id not in self.stories:
            raise NotFoundError(f"Story not found: {story_id}")
        self.updated[story_id] = (entities, themes, processing_status)

    def update_story_sentiment(self, story_id: str, sentiment, processing_status: str) -> None:
        if story_id not in self.stories:
            raise NotFoundError(f"Story not found: {story_id}")
        self.updated[story_id] = (sentiment, processing_status)


class FakeLLM(LLMPort):
    """In-memory LLM fake that returns canned responses."""

    def __init__(self, entities=None, themes=None):
        self._entities = entities or [{"name": "CI pipeline", "type": "tool"}]
        self._themes = themes or ["automation friction"]

    def extract_entities(self, story_text: str) -> EntityExtraction:
        return EntityExtraction(entities=self._entities)

    def extract_themes(self, story_text: str) -> list:
        return self._themes

    def extract_relationships(self, story_text: str) -> list:
        return []

    def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
        return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

    def synthesize_insights(self, context):
        from src.domain.models import InsightOutput
        return InsightOutput(narrative="")


class FailingLLM(LLMPort):
    """LLM fake that always raises LLMError."""

    def extract_entities(self, story_text: str) -> EntityExtraction:
        raise LLMError("API unavailable")

    def extract_themes(self, story_text: str) -> list:
        raise LLMError("API unavailable")

    def extract_relationships(self, story_text: str) -> list:
        raise LLMError("API unavailable")

    def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
        raise LLMError("API unavailable")

    def synthesize_insights(self, context):
        raise LLMError("API unavailable")


# ── Test 1: can instantiate service ───────────────────────────────────────────

def test_entity_extraction_service_can_be_created():
    """EntityExtractionService accepts storage and llm dependencies."""
    from src.services.entity_extraction import EntityExtractionService

    storage = FakeStorage()
    llm = FakeLLM()
    service = EntityExtractionService(storage=storage, llm=llm)

    assert service is not None


# ── Test 2: calls LLM with story text ─────────────────────────────────────────

def test_extract_for_story_calls_llm_with_story_text():
    """Service passes story text to the LLM."""
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})

    calls = []

    class CapturingLLM(FakeLLM):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            calls.append(story_text)
            return super().extract_entities(story_text)

    service = EntityExtractionService(storage=storage, llm=CapturingLLM())
    service.extract_for_story(story.id)

    assert len(calls) == 1
    assert calls[0] == story.story_text


# ── Test 3: stores extracted entities ─────────────────────────────────────────

def test_extract_for_story_stores_entities_in_storage():
    """Extracted entities are persisted via storage.update_story_entities."""
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})
    llm = FakeLLM(entities=[{"name": "CI pipeline", "type": "tool"}])

    service = EntityExtractionService(storage=storage, llm=llm)
    service.extract_for_story(story.id)

    assert story.id in storage.updated
    entities, themes, status = storage.updated[story.id]
    assert entities == [{"name": "CI pipeline", "type": "tool"}]


# ── Test 4: sets processing_status to "processed" ────────────────────────────

def test_extract_for_story_sets_status_processed_on_success():
    """Successful extraction sets processing_status to 'processed'."""
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})

    service = EntityExtractionService(storage=storage, llm=FakeLLM())
    service.extract_for_story(story.id)

    _, _, status = storage.updated[story.id]
    assert status == "processed"


# ── Test 5: LLM failure sets status to "failed" without raising ───────────────

def test_extract_for_story_handles_llm_failure_gracefully():
    """LLM errors are caught; status set to 'failed'; no exception raised."""
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})

    service = EntityExtractionService(storage=storage, llm=FailingLLM())

    # Must not raise
    service.extract_for_story(story.id)

    assert story.id in storage.updated
    _, _, status = storage.updated[story.id]
    assert status == "failed"


# ── Test 6: LLM failure stores empty entities/themes ─────────────────────────

def test_extract_for_story_stores_empty_on_llm_failure():
    """On LLM failure, empty entities and themes are stored."""
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})

    service = EntityExtractionService(storage=storage, llm=FailingLLM())
    service.extract_for_story(story.id)

    entities, themes, _ = storage.updated[story.id]
    assert entities == []
    assert themes == []


# ── Test 7: story not found propagates NotFoundError ──────────────────────────

def test_extract_for_story_raises_not_found_for_missing_story():
    """NotFoundError propagates when story does not exist."""
    from src.services.entity_extraction import EntityExtractionService

    storage = FakeStorage()  # empty
    service = EntityExtractionService(storage=storage, llm=FakeLLM())

    with pytest.raises(NotFoundError):
        service.extract_for_story("nonexistent-id")


# ── Test 8: stores themes returned by extract_themes() ────────────────────────

def test_extract_for_story_stores_themes_from_extract_themes():
    """Themes returned by extract_themes() are persisted as-is.

    extract_themes() returns List[str] directly — no normalisation needed.
    """
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})
    llm = FakeLLM(themes=["automation friction", "process overhead"])

    service = EntityExtractionService(storage=storage, llm=llm)
    service.extract_for_story(story.id)

    _, themes, _ = storage.updated[story.id]
    assert themes == ["automation friction", "process overhead"]
    assert all(isinstance(t, str) for t in themes)


# ── Test 10: themes come from extract_themes(), not extract_entities() ─────────

def test_extract_for_story_themes_come_from_extract_themes():
    """Themes are sourced from extract_themes(), not bundled with entities.

    The dedicated extract_themes() call is the canonical source of Story.themes.
    extract_entities() may also return themes but those are ignored.
    """
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})

    class DivergentLLM(FakeLLM):
        """Returns a distinct theme list from extract_themes() to prove it is used."""

        def extract_themes(self, story_text: str) -> list:
            return ["dedicated theme"]

    service = EntityExtractionService(storage=storage, llm=DivergentLLM())
    service.extract_for_story(story.id)

    _, themes, _ = storage.updated[story.id]
    assert themes == ["dedicated theme"]


# ── Test 9: extract_themes() failure is atomic — entities also empty ───────────

def test_extract_for_story_is_atomic_on_theme_failure():
    """If extract_themes() fails after extract_entities() succeeds, all are empty.

    Failure semantics are atomic: a partial extraction is worse than none
    because it leaves the story in an inconsistent state.
    """
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})

    class ThemeFailingLLM(FakeLLM):
        def extract_themes(self, story_text: str) -> list:
            raise LLMError("theme extraction failed")

    service = EntityExtractionService(storage=storage, llm=ThemeFailingLLM())
    service.extract_for_story(story.id)  # must not raise

    entities, themes, status = storage.updated[story.id]
    assert status == "failed"
    assert entities == []
    assert themes == []


# ── Tests for graph_projection wiring ─────────────────────────────────────────

class FakeGraphProjection:
    """Records project_story calls."""

    def __init__(self):
        self.calls = []

    def project_story(self, story_id: str) -> None:
        self.calls.append(story_id)


def test_extract_for_story_triggers_graph_projection_on_success():
    """On successful extraction, graph_projection.project_story() is called."""
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})
    graph_projection = FakeGraphProjection()

    service = EntityExtractionService(storage=storage, llm=FakeLLM(), graph_projection=graph_projection)
    service.extract_for_story(story.id)

    assert graph_projection.calls == [story.id]


def test_extract_for_story_skips_graph_projection_on_failure():
    """On LLM failure, graph_projection is not called."""
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})
    graph_projection = FakeGraphProjection()

    service = EntityExtractionService(storage=storage, llm=FailingLLM(), graph_projection=graph_projection)
    service.extract_for_story(story.id)

    assert graph_projection.calls == []


def test_extract_for_story_works_without_graph_projection():
    """graph_projection=None is backwards compatible — no AttributeError raised."""
    from src.services.entity_extraction import EntityExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})

    service = EntityExtractionService(storage=storage, llm=FakeLLM())  # no graph_projection
    service.extract_for_story(story.id)  # must not raise

    _, _, status = storage.updated[story.id]
    assert status == "processed"
