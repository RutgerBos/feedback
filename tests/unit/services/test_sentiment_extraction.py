"""Tests for SentimentExtractionService."""

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


_DEFAULT_SENTIMENT = SentimentAnalysis(
    emotion_markers=["frustration", "relief"],
    process_sentiment="negative",
    outcome_sentiment="positive",
)


class FakeStorage(StoragePort):
    """In-memory storage fake for unit tests."""

    def __init__(self, stories: dict = None):
        self.stories = stories or {}
        self.sentiment_updates: dict = {}  # story_id -> (sentiment, status)

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
        pass

    def update_story_sentiment(self, story_id: str, sentiment: SentimentAnalysis | None, processing_status: str) -> None:
        if story_id not in self.stories:
            raise NotFoundError(f"Story not found: {story_id}")
        self.sentiment_updates[story_id] = (sentiment, processing_status)


class FakeLLM(LLMPort):
    """In-memory LLM fake that returns canned responses."""

    def __init__(self, sentiment: SentimentAnalysis = None):
        self._sentiment = sentiment or _DEFAULT_SENTIMENT

    def extract_entities(self, story_text: str) -> EntityExtraction:
        return EntityExtraction(entities=[])

    def extract_themes(self, story_text: str) -> list:
        return []

    def extract_relationships(self, story_text: str) -> list:
        return []

    def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
        return self._sentiment

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

def test_sentiment_extraction_service_can_be_created():
    """SentimentExtractionService accepts storage and llm dependencies."""
    from src.services.sentiment_extraction import SentimentExtractionService

    service = SentimentExtractionService(storage=FakeStorage(), llm=FakeLLM())

    assert service is not None


# ── Test 2: calls LLM with story text ─────────────────────────────────────────

def test_extract_for_story_calls_llm_with_story_text():
    """Service passes story text to llm.extract_sentiment()."""
    from src.services.sentiment_extraction import SentimentExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})
    calls = []

    class CapturingLLM(FakeLLM):
        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            calls.append(story_text)
            return super().extract_sentiment(story_text)

    service = SentimentExtractionService(storage=storage, llm=CapturingLLM())
    service.extract_for_story(story.id)

    assert len(calls) == 1
    assert calls[0] == story.story_text


# ── Test 3: stores sentiment in storage ───────────────────────────────────────

def test_extract_for_story_stores_sentiment_in_storage():
    """Extracted sentiment is persisted via storage.update_story_sentiment."""
    from src.services.sentiment_extraction import SentimentExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})
    llm = FakeLLM(sentiment=_DEFAULT_SENTIMENT)

    service = SentimentExtractionService(storage=storage, llm=llm)
    service.extract_for_story(story.id)

    assert story.id in storage.sentiment_updates
    sentiment, _ = storage.sentiment_updates[story.id]
    assert sentiment.emotion_markers == ["frustration", "relief"]
    assert sentiment.process_sentiment == "negative"
    assert sentiment.outcome_sentiment == "positive"


# ── Test 4: sets processing_status to "processed" on success ──────────────────

def test_extract_for_story_sets_status_processed_on_success():
    """Successful extraction sets processing_status to 'processed'."""
    from src.services.sentiment_extraction import SentimentExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})

    service = SentimentExtractionService(storage=storage, llm=FakeLLM())
    service.extract_for_story(story.id)

    _, status = storage.sentiment_updates[story.id]
    assert status == "processed"


# ── Test 5: LLM failure stores None sentiment, sets status "failed" ───────────

def test_extract_for_story_handles_llm_failure_gracefully():
    """LLM errors are caught; None sentiment stored; status set to 'failed'; no exception."""
    from src.services.sentiment_extraction import SentimentExtractionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})

    service = SentimentExtractionService(storage=storage, llm=FailingLLM())

    # Must not raise
    service.extract_for_story(story.id)

    assert story.id in storage.sentiment_updates
    sentiment, status = storage.sentiment_updates[story.id]
    assert sentiment is None
    assert status == "failed"


# ── Test 6: NotFoundError propagates ──────────────────────────────────────────

def test_extract_for_story_raises_not_found_for_missing_story():
    """NotFoundError propagates when story does not exist."""
    from src.services.sentiment_extraction import SentimentExtractionService

    storage = FakeStorage()  # empty
    service = SentimentExtractionService(storage=storage, llm=FakeLLM())

    with pytest.raises(NotFoundError):
        service.extract_for_story("nonexistent-id")
