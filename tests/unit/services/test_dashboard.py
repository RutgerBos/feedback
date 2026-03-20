"""Tests for DashboardService."""

from datetime import UTC, datetime

from src.domain.models import (
    Story,
    TriadCoordinates,
    TriadPlacement,
)
from src.ports.storage import StoragePort

# ── Fakes ─────────────────────────────────────────────────────────────────────


def make_story(
    story_id: str = "s1",
    themes: list[str] | None = None,
    entities: list[dict] | None = None,
    timestamp: datetime | None = None,
) -> Story:
    return Story(
        id=story_id,
        story_text="The CI pipeline kept failing and blocked our team. " * 2,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
        processing_status="processed",
        themes=themes or [],
        entities=entities or [],
        timestamp=timestamp or datetime(2026, 3, 1, tzinfo=UTC),
    )


class FakeStorage(StoragePort):
    def __init__(self, stories: list[Story] | None = None):
        self._stories = stories or []

    def save_story(self, story: Story) -> str:
        return story.id

    def get_story(self, story_id: str) -> Story:
        for s in self._stories:
            if s.id == story_id:
                return s
        raise KeyError(story_id)

    def count_stories(self) -> int:
        return len(self._stories)

    def list_stories(self, limit: int = 20, offset: int = 0) -> list[Story]:
        return self._stories[offset: offset + limit]

    def update_story_entities(self, story_id, entities, themes, processing_status):
        pass

    def update_story_sentiment(self, story_id, sentiment, processing_status):
        pass


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_dashboard_returns_total_story_count():
    """DashboardService.get_data returns total_stories matching the store count."""
    from src.services.dashboard import DashboardService

    stories = [make_story("s1"), make_story("s2"), make_story("s3")]
    service = DashboardService(storage=FakeStorage(stories))

    data = service.get_data()

    assert data.total_stories == 3


def test_dashboard_empty_store_returns_zeros():
    """DashboardService.get_data handles an empty store gracefully."""
    from src.services.dashboard import DashboardService

    service = DashboardService(storage=FakeStorage([]))

    data = service.get_data()

    assert data.total_stories == 0
    assert data.top_themes == []
    assert data.top_entities == []


def test_dashboard_top_themes_sorted_by_count():
    """top_themes is ordered by frequency, highest first."""
    from src.services.dashboard import DashboardService

    stories = [
        make_story("s1", themes=["automation friction", "tooling"]),
        make_story("s2", themes=["automation friction", "developer experience"]),
        make_story("s3", themes=["tooling"]),
    ]
    service = DashboardService(storage=FakeStorage(stories))

    data = service.get_data()

    assert data.top_themes[0]["name"] == "automation friction"
    assert data.top_themes[0]["count"] == 2
    assert data.top_themes[1]["name"] == "tooling"
    assert data.top_themes[1]["count"] == 2


def test_dashboard_top_entities_sorted_by_count():
    """top_entities is ordered by frequency, highest first."""
    from src.services.dashboard import DashboardService

    stories = [
        make_story("s1", entities=[{"name": "CI pipeline", "type": "tool"}, {"name": "deployment", "type": "process"}]),
        make_story("s2", entities=[{"name": "CI pipeline", "type": "tool"}]),
    ]
    service = DashboardService(storage=FakeStorage(stories))

    data = service.get_data()

    assert data.top_entities[0]["name"] == "CI pipeline"
    assert data.top_entities[0]["count"] == 2


def test_dashboard_top_themes_limited_to_ten():
    """top_themes returns at most 10 entries."""
    from src.services.dashboard import DashboardService

    themes_per_story = [f"theme-{i}" for i in range(15)]
    stories = [make_story("s1", themes=themes_per_story)]
    service = DashboardService(storage=FakeStorage(stories))

    data = service.get_data()

    assert len(data.top_themes) <= 10


def test_dashboard_top_entities_limited_to_ten():
    """top_entities returns at most 10 entries."""
    from src.services.dashboard import DashboardService

    entities = [{"name": f"entity-{i}", "type": "tool"} for i in range(15)]
    stories = [make_story("s1", entities=entities)]
    service = DashboardService(storage=FakeStorage(stories))

    data = service.get_data()

    assert len(data.top_entities) <= 10


def test_dashboard_filters_by_from_date():
    """Stories before from_date are excluded from aggregation."""
    from src.services.dashboard import DashboardService

    old = make_story("s1", themes=["old theme"], timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    new = make_story("s2", themes=["new theme"], timestamp=datetime(2026, 3, 15, tzinfo=UTC))
    service = DashboardService(storage=FakeStorage([old, new]))

    data = service.get_data(from_date=datetime(2026, 3, 1, tzinfo=UTC))

    theme_names = [t["name"] for t in data.top_themes]
    assert "new theme" in theme_names
    assert "old theme" not in theme_names


def test_dashboard_filters_by_to_date():
    """Stories after to_date are excluded from aggregation."""
    from src.services.dashboard import DashboardService

    old = make_story("s1", themes=["old theme"], timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    new = make_story("s2", themes=["new theme"], timestamp=datetime(2026, 3, 15, tzinfo=UTC))
    service = DashboardService(storage=FakeStorage([old, new]))

    data = service.get_data(to_date=datetime(2026, 2, 1, tzinfo=UTC))

    theme_names = [t["name"] for t in data.top_themes]
    assert "old theme" in theme_names
    assert "new theme" not in theme_names


def test_dashboard_recent_stories_included():
    """get_data returns a list of recent story IDs."""
    from src.services.dashboard import DashboardService

    stories = [make_story(f"s{i}") for i in range(5)]
    service = DashboardService(storage=FakeStorage(stories))

    data = service.get_data()

    assert len(data.recent_story_ids) > 0
    assert len(data.recent_story_ids) <= 5


def test_dashboard_distinct_counts_reflect_full_set_not_cap():
    """distinct_theme_count and distinct_entity_count are the true uniques, not capped at 10."""
    from src.services.dashboard import DashboardService

    themes_per_story = [f"theme-{i}" for i in range(15)]
    entities_per_story = [{"name": f"entity-{i}", "type": "tool"} for i in range(12)]
    stories = [make_story("s1", themes=themes_per_story, entities=entities_per_story)]
    service = DashboardService(storage=FakeStorage(stories))

    data = service.get_data()

    assert data.distinct_theme_count == 15
    assert data.distinct_entity_count == 12
    assert len(data.top_themes) == 10   # still capped
    assert len(data.top_entities) == 10  # still capped


def test_dashboard_to_date_midnight_includes_full_day():
    """to_date at midnight (00:00:00) is treated as end-of-day so same-day stories are included."""
    from src.services.dashboard import DashboardService

    story = make_story("s1", timestamp=datetime(2026, 3, 15, 14, 0, 0, tzinfo=UTC))
    service = DashboardService(storage=FakeStorage([story]))

    # to_date is midnight of March 15 — should still include 14:00 story
    data = service.get_data(to_date=datetime(2026, 3, 15, 0, 0, 0, tzinfo=UTC))

    assert data.total_stories == 1
