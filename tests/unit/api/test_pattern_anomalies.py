"""API contract tests for GET /api/patterns/anomalies."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.models import Story
from src.ports.errors import GraphError, StorageError


class FakeGraph:
    def __init__(self, neighbourhoods=None):
        self.neighbourhoods = neighbourhoods or []

    def find_story_neighbourhoods(self):
        return self.neighbourhoods


class FakeStorage:
    def __init__(self, stories=None):
        self.stories = stories or []

    def list_stories(self, limit=20, offset=0, from_date=None, to_date=None):
        return self.stories[offset : offset + limit]


def make_story(story_id: str) -> Story:
    return Story(
        id=story_id,
        story_text="A sufficiently detailed account of an unusual delivery experience.",
        processing_status="processed",
    )


def make_client(graph=None, storage=None) -> TestClient:
    from src.api.patterns import router
    from src.composition import get_anomaly_detection_service

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_anomaly_detection_service] = lambda: __import__(
        "src.services.anomaly_detection", fromlist=["AnomalyDetectionService"]
    ).AnomalyDetectionService(graph or FakeGraph(), storage or FakeStorage())
    return TestClient(app)


def test_get_anomalies_serializes_ranked_reasons():
    with make_client(
        FakeGraph([("isolated", [])]), FakeStorage([make_story("isolated")])
    ) as client:
        response = client.get("/api/patterns/anomalies")

    assert response.status_code == 200
    assert response.json() == {
        "anomalies": [{
            "story_id": "isolated",
            "score": 1.0,
            "reasons": [{
                "kind": "disconnected",
                "score": 1.0,
                "explanation": "Story has no proximity neighbours.",
            }],
        }]
    }


def test_get_anomalies_validates_limit():
    with make_client() as client:
        assert client.get("/api/patterns/anomalies?limit=0").status_code == 422
        assert client.get("/api/patterns/anomalies?limit=101").status_code == 422


def test_get_anomalies_applies_limit_after_ranking():
    stories = [make_story("b"), make_story("a")]
    with make_client(FakeGraph([("b", []), ("a", [])]), FakeStorage(stories)) as client:
        response = client.get("/api/patterns/anomalies?limit=1")

    assert [entry["story_id"] for entry in response.json()["anomalies"]] == ["a"]


def test_get_anomalies_maps_graph_and_storage_failures_to_503():
    class FailingGraph(FakeGraph):
        def find_story_neighbourhoods(self):
            raise GraphError("secret graph details")

    class FailingStorage(FakeStorage):
        def list_stories(self, limit=20, offset=0, from_date=None, to_date=None):
            raise StorageError("secret storage details")

    with make_client(FailingGraph(), FakeStorage()) as client:
        graph_response = client.get("/api/patterns/anomalies")
    with make_client(FakeGraph(), FailingStorage()) as client:
        storage_response = client.get("/api/patterns/anomalies")

    assert graph_response.status_code == 503
    assert graph_response.json() == {"detail": "Pattern data unavailable"}
    assert storage_response.status_code == 503
    assert storage_response.json() == {"detail": "Pattern data unavailable"}
