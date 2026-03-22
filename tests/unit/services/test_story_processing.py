"""Unit tests for StoryProcessingService."""

import pytest


class FakeStorage:
    def __init__(self, story_id="s1"):
        self._story_id = story_id

    def get_story(self, story_id):
        from src.domain.models import Story, StorySignification
        from datetime import datetime
        return Story(
            id=story_id,
            story_text="A story about CI friction that is at least fifty chars.",
            signification=StorySignification(responses=[]),
            timestamp=datetime.utcnow(),
        )


class FakeGraph:
    def __init__(self):
        self.saved = []

    def save_story_node(self, story_id, triads, timestamp):
        self.saved.append(story_id)


class FakeEntityService:
    def __init__(self):
        self.processed = []

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
    from src.services.story_processing import StoryProcessingService
    from src.ports.errors import GraphError

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
    from src.services.story_processing import StoryProcessingService
    from src.ports.errors import GraphError

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
