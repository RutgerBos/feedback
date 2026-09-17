"""Tests for deterministic MVP anomaly detection."""

import pytest

from src.domain.models import Story, StorySignification, TriadCoordinates, TriadResponseItem
from src.ports.errors import GraphError, StorageError
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort


def make_story(
    story_id: str,
    *,
    x: float = 0.5,
    y: float = 0.5,
    themes: list[str] | None = None,
    entities: list[str] | None = None,
    status: str = "processed",
) -> Story:
    return Story(
        id=story_id,
        story_text="A detailed account of delivery friction and team learning. " * 2,
        signification=StorySignification(
            responses=[
                TriadResponseItem(
                    signifier_id="workflow_nature",
                    coordinates=TriadCoordinates(x=x, y=y),
                )
            ]
        ),
        processing_status=status,
        themes=themes or [],
        entities=[{"name": name, "type": "topic"} for name in (entities or [])],
    )


class FakeGraph(GraphPort):
    def __init__(self, neighbourhoods: list[tuple[str, list[str]]] | None = None):
        self.neighbourhoods = neighbourhoods or []

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
    def find_story_neighbourhoods(self): return self.neighbourhoods


class FakeStorage(StoragePort):
    def __init__(self, stories: list[Story] | None = None):
        self.stories = stories or []
        self.list_calls: list[tuple[int, int]] = []

    def save_story(self, story): return story.id
    def get_story(self, story_id):
        return next(story for story in self.stories if story.id == story_id)
    def count_stories(self, from_date=None, to_date=None): return len(self.stories)
    def list_stories(self, limit=20, offset=0, from_date=None, to_date=None):
        self.list_calls.append((limit, offset))
        return self.stories[offset : offset + limit]
    def update_story_entities(self, story_id, entities, themes, entity_status): pass
    def update_story_sentiment(self, story_id, sentiment, sentiment_status): pass
    def find_story_ids_requiring_processing(self): return []


def test_empty_dataset_returns_no_anomalies():
    from src.services.anomaly_detection import AnomalyDetectionService

    result = AnomalyDetectionService(FakeGraph(), FakeStorage()).find_anomalies(limit=25)

    assert result.anomalies == []


def test_disconnected_processed_story_is_anomalous():
    from src.services.anomaly_detection import AnomalyDetectionService

    story = make_story("isolated")
    result = AnomalyDetectionService(
        FakeGraph([("isolated", [])]), FakeStorage([story])
    ).find_anomalies(limit=25)

    assert result.anomalies[0].story_id == "isolated"
    assert result.anomalies[0].score == 1.0
    assert result.anomalies[0].reasons[0].kind == "disconnected"


def test_storage_only_story_is_disconnected_and_unprocessed_story_is_ignored():
    from src.services.anomaly_detection import AnomalyDetectionService

    result = AnomalyDetectionService(
        FakeGraph(),
        FakeStorage([make_story("stored"), make_story("pending", status="pending")]),
    ).find_anomalies(limit=25)

    assert [anomaly.story_id for anomaly in result.anomalies] == ["stored"]


def test_unusually_low_and_high_nonzero_degree_are_detected():
    from src.services.anomaly_detection import AnomalyDetectionService

    ids = [f"s{i}" for i in range(10)]
    degrees = [1, 5, 5, 5, 5, 5, 5, 5, 5, 9]
    neighbourhoods = [
        (story_id, [f"external-{story_id}-{i}" for i in range(degree)])
        for story_id, degree in zip(ids, degrees, strict=True)
    ]
    result = AnomalyDetectionService(
        FakeGraph(neighbourhoods), FakeStorage([make_story(story_id) for story_id in ids])
    ).find_anomalies(limit=25)

    reasons = {a.story_id: {reason.kind for reason in a.reasons} for a in result.anomalies}
    assert "low_degree" in reasons["s0"]
    assert "high_degree" in reasons["s9"]


def test_coordinate_outlier_is_detected_but_fence_equality_and_sparse_data_are_not():
    from src.services.anomaly_detection import AnomalyDetectionService

    stories = [
        make_story("s1", x=0.10),
        make_story("s2", x=0.11),
        make_story("s3", x=0.12),
        make_story("s4", x=0.13),
        make_story("outlier", x=0.90),
    ]
    graph = FakeGraph([(story.id, ["neighbour"]) for story in stories])

    result = AnomalyDetectionService(graph, FakeStorage(stories)).find_anomalies(limit=25)

    outlier = next(a for a in result.anomalies if a.story_id == "outlier")
    reason = next(reason for reason in outlier.reasons if reason.kind == "coordinate_outlier")
    assert "workflow_nature x-coordinate" in reason.explanation

    sparse = stories[:3]
    sparse_result = AnomalyDetectionService(
        FakeGraph([(story.id, ["neighbour"]) for story in sparse]), FakeStorage(sparse)
    ).find_anomalies(limit=25)
    assert all(
        reason.kind != "coordinate_outlier"
        for anomaly in sparse_result.anomalies
        for reason in anomaly.reasons
    )


def test_profile_mismatch_normalizes_names_and_ignores_empty_profiles():
    from src.services.anomaly_detection import AnomalyDetectionService

    stories = [
        make_story("match-a", themes=[" Delivery   Flow "], entities=["CI"]),
        make_story("match-b", themes=["delivery flow"], entities=["ci"]),
        make_story("mismatch", themes=["customer research"], entities=["Interviews"]),
        make_story("empty-a"),
        make_story("empty-b"),
    ]
    graph = FakeGraph([
        ("match-a", ["match-b"]),
        ("match-b", ["match-a"]),
        ("mismatch", ["match-a"]),
        ("empty-a", ["empty-b"]),
        ("empty-b", ["empty-a"]),
    ])

    result = AnomalyDetectionService(graph, FakeStorage(stories)).find_anomalies(limit=25)

    reasons = {a.story_id: {reason.kind for reason in a.reasons} for a in result.anomalies}
    assert "match-a" not in reasons
    assert "match-b" not in reasons
    assert "profile_mismatch" in reasons["mismatch"]
    assert "empty-a" not in reasons
    assert "empty-b" not in reasons


def test_ranking_reasons_and_limit_are_deterministic():
    from src.services.anomaly_detection import AnomalyDetectionService

    stories = [make_story("b"), make_story("a")]
    result = AnomalyDetectionService(
        FakeGraph([("b", []), ("a", [])]), FakeStorage(stories)
    ).find_anomalies(limit=1)

    assert [a.story_id for a in result.anomalies] == ["a"]
    assert result.anomalies[0].score == max(r.score for r in result.anomalies[0].reasons)


def test_storage_is_read_in_fixed_size_pages():
    from src.services.anomaly_detection import _PAGE_SIZE, AnomalyDetectionService

    stories = [make_story(f"s{i}") for i in range(_PAGE_SIZE + 1)]
    storage = FakeStorage(stories)
    AnomalyDetectionService(FakeGraph(), storage).find_anomalies(limit=1)

    assert storage.list_calls == [(_PAGE_SIZE, 0), (_PAGE_SIZE, _PAGE_SIZE)]


def test_graph_and_storage_errors_propagate():
    from src.services.anomaly_detection import AnomalyDetectionService

    class FailingGraph(FakeGraph):
        def find_story_neighbourhoods(self):
            raise GraphError("down")

    class FailingStorage(FakeStorage):
        def list_stories(self, limit=20, offset=0, from_date=None, to_date=None):
            raise StorageError("down")

    with pytest.raises(GraphError):
        AnomalyDetectionService(FailingGraph(), FakeStorage()).find_anomalies(limit=1)
    with pytest.raises(StorageError):
        AnomalyDetectionService(FakeGraph(), FailingStorage()).find_anomalies(limit=1)
