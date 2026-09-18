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
                            coordinates=TriadCoordinates(x=0.4, y=0.4),
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
    from src.composition import get_storage

    app.dependency_overrides[get_storage] = lambda: FakeStorage()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/signifiers/workflow_nature/stories/query",
                json={
                    "selection": {
                        "kind": "polygon",
                        "points": [
                            {"x": 0.5, "y": 0.0},
                            {"x": 0.25, "y": 0.5},
                            {"x": 0.75, "y": 0.5},
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
                "coordinates": {"x": 0.4, "y": 0.4},
                "timestamp": "2026-01-02T00:00:00Z",
                "context_metadata": {
                    "department": "engineering",
                },
            }
        ],
        "limit": 50,
        "offset": 0,
    }


def test_query_rejects_selection_points_outside_triad_triangle():
    from src.api.main import app
    from src.composition import get_storage

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
                            {"x": 0.25, "y": 0.5},
                            {"x": 0.75, "y": 0.5},
                        ],
                    }
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_query_rejects_polygon_without_area():
    from src.api.main import app
    from src.composition import get_storage

    app.dependency_overrides[get_storage] = lambda: FakeStorage()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/signifiers/workflow_nature/stories/query",
                json={
                    "selection": {
                        "kind": "polygon",
                        "points": [
                            {"x": 0.5, "y": 0.2},
                            {"x": 0.5, "y": 0.4},
                            {"x": 0.5, "y": 0.6},
                        ],
                    }
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_query_rejects_excessively_complex_polygon():
    from src.api.main import app
    from src.composition import get_storage

    points = [
        {"x": 0.5, "y": 0.0},
        {"x": 0.25, "y": 0.5},
        {"x": 0.75, "y": 0.5},
    ] * 17
    app.dependency_overrides[get_storage] = lambda: FakeStorage()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/signifiers/workflow_nature/stories/query",
                json={"selection": {"kind": "polygon", "points": points}},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_query_ignores_storage_story_without_requested_signifier():
    from src.api.main import app
    from src.composition import get_storage

    class MismatchedStorage(FakeStorage):
        def find_stories_in_polygon(self, *args, **kwargs):
            story = super().find_stories_in_polygon(*args, **kwargs)[0]
            return [story.model_copy(update={
                "signification": StorySignification(
                    responses=[
                        TriadResponseItem(
                            signifier_id="different_signifier",
                            coordinates=TriadCoordinates(x=0.5, y=0.5),
                        )
                    ]
                )
            })]

    app.dependency_overrides[get_storage] = lambda: MismatchedStorage()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/signifiers/workflow_nature/stories/query",
                json={
                    "selection": {
                        "kind": "polygon",
                        "points": [
                            {"x": 0.5, "y": 0.0},
                            {"x": 0.25, "y": 0.5},
                            {"x": 0.75, "y": 0.5},
                        ],
                    }
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["stories"] == []


def test_query_includes_machine_overlays_only_when_requested():
    from src.api.main import app
    from src.composition import get_storage

    app.dependency_overrides[get_storage] = lambda: FakeStorage()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/signifiers/workflow_nature/stories/query",
                json={
                    "selection": {
                        "kind": "polygon",
                        "points": [
                            {"x": 0.5, "y": 0.0},
                            {"x": 0.25, "y": 0.5},
                            {"x": 0.75, "y": 0.5},
                        ],
                    },
                    "include_overlays": True,
                },
            )
    finally:
        app.dependency_overrides.clear()

    story = response.json()["stories"][0]
    assert story["themes"] == ["automation friction"]
    assert story["entities"] == [{"name": "CI pipeline", "type": "tool"}]


def test_query_maps_storage_failure_to_generic_503():
    from src.api.main import app
    from src.composition import get_storage
    from src.ports.errors import StorageError

    class FailingStorage:
        def find_stories_in_polygon(self, *args, **kwargs):
            raise StorageError("secret database details")

    app.dependency_overrides[get_storage] = lambda: FailingStorage()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/signifiers/workflow_nature/stories/query",
                json={
                    "selection": {
                        "kind": "polygon",
                        "points": [
                            {"x": 0.5, "y": 0.0},
                            {"x": 0.25, "y": 0.5},
                            {"x": 0.75, "y": 0.5},
                        ],
                    }
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Story data unavailable"}
