"""API contract tests for spatial story drill-down by signifier."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.domain.models import (
    ContextMetadata,
    Story,
    StorySignification,
    TriadCoordinates,
    TriadResponseItem,
)


class FakeStorage:
    def find_stories_in_polygon(self, signifier_id, polygon_points, limit=50, offset=0):
        return [
            Story(
                id="story-1",
                story_text="A detailed participant account of a difficult deployment.",
                schema_version=2,
                signification=StorySignification(
                    headline="Deployment friction",
                    responses=[
                        TriadResponseItem(
                            signifier_id="workflow_nature",
                            coordinates=TriadCoordinates(x=0.25, y=0.4),
                        )
                    ],
                ),
                context=ContextMetadata(department="engineering"),
                timestamp=datetime(2026, 1, 2, tzinfo=UTC),
                themes=["automation friction"],
                entities=[{"name": "CI pipeline", "type": "tool"}],
            )
        ]


def test_query_signifier_polygon_returns_evidence_without_overlays_by_default():
    from src.api.main import app
    from src.api.stories import get_storage

    app.dependency_overrides[get_storage] = lambda: FakeStorage()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/signifiers/workflow_nature/stories/query",
                json={
                    "selection": {
                        "kind": "polygon",
                        "points": [
                            {"x": 0.0, "y": 0.0},
                            {"x": 0.5, "y": 0.8},
                            {"x": 0.5, "y": 0.0},
                        ],
                    }
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "stories": [
            {
                "id": "story-1",
                "headline": "Deployment friction",
                "story_excerpt": "A detailed participant account of a difficult deployment.",
                "coordinates": {"x": 0.25, "y": 0.4},
                "timestamp": "2026-01-02T00:00:00Z",
                "context": {
                    "department": "engineering",
                    "role": None,
                    "tool_context": None,
                },
            }
        ],
        "limit": 50,
        "offset": 0,
    }
