"""Tests for EntityExtractionService."""

import pytest
from src.ports.storage import StoragePort
from src.ports.llm import LLMPort, EntityExtraction
from src.ports.errors import LLMError, NotFoundError
from src.domain.models import Story, TriadPlacement, TriadCoordinates


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

    def count_stories(self) -> int:
        return len(self.stories)

    def list_stories(self, limit: int = 20, offset: int = 0) -> list:
        return list(self.stories.values())[offset:offset + limit]

    def update_story_entities(self, story_id: str, entities: list, themes: list, processing_status: str) -> None:
        if story_id not in self.stories:
            raise NotFoundError(f"Story not found: {story_id}")
        self.updated[story_id] = (entities, themes, processing_status)


class FakeLLM(LLMPort):
    """In-memory LLM fake that returns canned responses."""

    def __init__(self, entities=None, themes=None):
        self._entities = entities or [{"name": "CI pipeline", "type": "tool"}]
        self._themes = themes or ["automation friction"]

    def extract_entities(self, story_text: str) -> EntityExtraction:
        return EntityExtraction(entities=self._entities, themes=[])

    def extract_themes(self, story_text: str) -> list:
        return self._themes

    def extract_relationships(self, story_text: str) -> list:
        return []


class FailingLLM(LLMPort):
    """LLM fake that always raises LLMError."""

    def extract_entities(self, story_text: str) -> EntityExtraction:
        raise LLMError("API unavailable")

    def extract_themes(self, story_text: str) -> list:
        raise LLMError("API unavailable")

    def extract_relationships(self, story_text: str) -> list:
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
