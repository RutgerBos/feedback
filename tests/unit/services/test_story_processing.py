"""Unit tests for StoryProcessingService."""

import pytest


class FakeStorage:
    def __init__(self, story_id="s1", entity_status="pending", sentiment_status="pending"):
        self._story_id = story_id
        self.entity_status = entity_status
        self.sentiment_status = sentiment_status

    def get_story(self, story_id):
        from datetime import UTC, datetime

        from src.domain.models import Story, StorySignification
        return Story(
            id=story_id,
            story_text="A story about CI friction that is at least fifty chars.",
            signification=StorySignification(responses=[]),
            timestamp=datetime.now(UTC),
            entity_status=self.entity_status,
            sentiment_status=self.sentiment_status,
        )


class FakeGraph:
    def __init__(self):
        self.saved = []

    def save_story_node(self, story_id, triads, timestamp):
        self.saved.append(story_id)


class FakeEntityService:
    def __init__(self):
        self.processed = []
        self.graph_projection = None

    def extract_for_story(self, story_id):
        self.processed.append(story_id)


class FakeSentimentService:
    def __init__(self):
        self.processed = []

    def extract_for_story(self, story_id):
        self.processed.append(story_id)


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_process_calls_graph_save_then_entity_then_sentiment():
    """process() runs graph→entity→sentiment in order."""
    from src.services.story_processing import StoryProcessingService

    order = []
    storage = FakeStorage()

    class OrderGraph(FakeGraph):
        def save_story_node(self, **kwargs):
            order.append("graph")

    class OrderEntity(FakeEntityService):
        def extract_for_story(self, story_id):
            order.append("entity")

    class OrderSentiment(FakeSentimentService):
        def extract_for_story(self, story_id):
            order.append("sentiment")

    svc = StoryProcessingService(
        storage=storage,
        graph=OrderGraph(),
        entity_service=OrderEntity(),
        sentiment_service=OrderSentiment(),
    )
    svc.process("s1")

    assert order == ["graph", "entity", "sentiment"]


def test_process_propagates_graph_error():
    """process() does not swallow GraphError from graph.save_story_node."""
    from src.ports.errors import GraphError
    from src.services.story_processing import StoryProcessingService

    class FailGraph(FakeGraph):
        def save_story_node(self, **kwargs):
            raise GraphError("Neo4j down")

    svc = StoryProcessingService(
        storage=FakeStorage(),
        graph=FailGraph(),
        entity_service=FakeEntityService(),
        sentiment_service=FakeSentimentService(),
    )

    with pytest.raises(GraphError):
        svc.process("s1")


def test_process_does_not_run_entity_if_graph_fails():
    """entity extraction is skipped when graph save fails."""
    from src.ports.errors import GraphError
    from src.services.story_processing import StoryProcessingService

    entity = FakeEntityService()

    class FailGraph(FakeGraph):
        def save_story_node(self, **kwargs):
            raise GraphError("Neo4j down")

    svc = StoryProcessingService(
        storage=FakeStorage(),
        graph=FailGraph(),
        entity_service=entity,
        sentiment_service=FakeSentimentService(),
    )

    with pytest.raises(GraphError):
        svc.process("s1")

    assert entity.processed == []


def test_process_reports_incomplete_when_an_extraction_fails():
    """The worker can distinguish recorded LLM failure from successful processing."""
    from src.services.story_processing import StoryProcessingService

    class FailedEntity(FakeEntityService):
        def extract_for_story(self, story_id):
            return False

    class SuccessfulSentiment(FakeSentimentService):
        def extract_for_story(self, story_id):
            return True

    svc = StoryProcessingService(
        storage=FakeStorage(),
        graph=FakeGraph(),
        entity_service=FailedEntity(),
        sentiment_service=SuccessfulSentiment(),
    )

    assert svc.process("s1") is False


def test_process_replays_persisted_entities_and_only_runs_incomplete_sentiment():
    """A retry preserves completed enrichment while repairing its graph projection."""
    from src.services.story_processing import StoryProcessingService

    class RecordingProjection:
        def __init__(self):
            self.projected = []

        def project_story(self, story_id):
            self.projected.append(story_id)

    projection = RecordingProjection()
    entity = FakeEntityService()
    entity.graph_projection = projection
    sentiment = FakeSentimentService()

    svc = StoryProcessingService(
        storage=FakeStorage(entity_status="processed", sentiment_status="pending"),
        graph=FakeGraph(),
        entity_service=entity,
        sentiment_service=sentiment,
    )

    assert svc.process("s1") is True
    assert entity.processed == []
    assert projection.projected == ["s1"]
    assert sentiment.processed == ["s1"]
