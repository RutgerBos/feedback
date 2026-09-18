"""Infrastructure proof that interrupted story processing is replay-safe."""

from datetime import UTC, datetime

import pytest
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from pymongo import MongoClient

from src.adapters.mongodb_storage import MongoDBStorageAdapter
from src.adapters.neo4j_graph import Neo4jGraphAdapter
from src.domain.models import (
    SentimentAnalysis,
    Story,
    StorySignification,
    TriadCoordinates,
    TriadResponseItem,
)
from src.ports.errors import GraphError
from src.ports.llm import EntityExtraction
from src.services.entity_extraction import EntityExtractionService
from src.services.graph_projection import GraphProjectionService
from src.services.proximity import ProximityCalculationService
from src.services.sentiment_extraction import SentimentExtractionService
from src.services.story_processing import StoryProcessingService
from src.workers.story_worker import StoryWorker

MONGO_URL = "mongodb://admin:password@localhost:27017/"
NEO4J_URL = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "password")
PREFIX = "test-retry-idempotency-"


class CountingLLM:
    def __init__(self) -> None:
        self.entity_calls = 0
        self.theme_calls = 0
        self.sentiment_calls = 0

    def extract_entities(self, story_text: str) -> EntityExtraction:
        self.entity_calls += 1
        return EntityExtraction(entities=[{"name": f"{PREFIX}pipeline", "type": "tool"}])

    def extract_themes(self, story_text: str) -> list[str]:
        self.theme_calls += 1
        return [f"{PREFIX}delivery"]

    def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
        self.sentiment_calls += 1
        return SentimentAnalysis(
            emotion_markers=["frustration"],
            process_sentiment="negative",
            outcome_sentiment="neutral",
        )


class FailFirstEntityProjection:
    def __init__(self, graph: Neo4jGraphAdapter) -> None:
        self._graph = graph
        self._failed = False

    def save_entity_nodes(self, story_id, entities):
        if not self._failed:
            self._failed = True
            raise GraphError("injected interruption after Mongo enrichment persistence")
        return self._graph.save_entity_nodes(story_id, entities)

    def __getattr__(self, name):
        return getattr(self._graph, name)


class Queue:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.completed: list[str] = []

    def enqueue(self, story_id: str) -> None:
        self.items.append(story_id)

    def dequeue(self, timeout=0):
        return self.items.pop(0) if self.items else None

    def complete(self, story_id: str) -> None:
        self.completed.append(story_id)


def _story(story_id: str, x: float, processing_status: str = "pending") -> Story:
    return Story(
        id=story_id,
        story_text="The delivery pipeline repeatedly failed and delayed the release for several days.",
        signification=StorySignification(
            responses=[
                TriadResponseItem(
                    signifier_id="workflow_nature",
                    coordinates=TriadCoordinates(x=x, y=0.5),
                )
            ]
        ),
        timestamp=datetime.now(UTC),
        processing_status=processing_status,
    )


@pytest.fixture
def retry_infrastructure():
    try:
        driver = GraphDatabase.driver(NEO4J_URL, auth=NEO4J_AUTH)
        driver.verify_connectivity()
    except (ServiceUnavailable, Exception):
        pytest.skip("Neo4j not reachable at localhost:7687")

    client = MongoClient(MONGO_URL)
    db = client["test_feedback_story_retry"]

    def cleanup() -> None:
        db.stories.delete_many({"_id": {"$regex": f"^{PREFIX}"}})
        with driver.session() as session:
            session.run(
                "MATCH (n) WHERE (n:Story AND n.story_id STARTS WITH $prefix) "
                "OR (n:Entity AND n.name STARTS WITH $prefix) "
                "OR (n:Theme AND n.name STARTS WITH $prefix) DETACH DELETE n",
                prefix=PREFIX,
            )

    cleanup()
    yield db, driver
    cleanup()
    driver.close()
    client.close()


def test_interrupted_processing_retries_without_duplicate_enrichment_or_graph_data(
    retry_infrastructure,
):
    db, driver = retry_infrastructure
    storage = MongoDBStorageAdapter(db)
    real_graph = Neo4jGraphAdapter(driver)
    graph = FailFirstEntityProjection(real_graph)
    llm = CountingLLM()
    target_id = f"{PREFIX}target"
    neighbour_id = f"{PREFIX}neighbour"

    storage.save_story(_story(target_id, 0.50))
    storage.save_story(_story(neighbour_id, 0.51, processing_status="processed"))
    real_graph.save_story_node(neighbour_id, [], datetime.now(UTC).isoformat())

    proximity = ProximityCalculationService(storage, graph, threshold=0.1)
    projection = GraphProjectionService(storage, graph, proximity)
    service = StoryProcessingService(
        storage,
        graph,
        EntityExtractionService(storage, llm, projection),
        SentimentExtractionService(storage, llm),
    )
    queue = Queue()
    worker = StoryWorker(queue, service, storage, dequeue_timeout=0, retry_base_delay=0)

    queue.enqueue(target_id)
    worker.run_once()
    interrupted = storage.get_story(target_id)
    assert interrupted.entity_status == "processed"
    assert interrupted.sentiment_status == "pending"
    assert interrupted.processing_status == "retrying"

    queue.enqueue(target_id)
    worker.run_once()
    completed = storage.get_story(target_id)
    enrichment = (completed.entities, completed.themes, completed.sentiment)
    assert completed.processing_status == "processed"
    assert completed.processing_attempts == 2
    assert completed.next_processing_at is None
    assert completed.processing_error is None

    def cardinalities() -> tuple[int, int, int, int]:
        with driver.session() as session:
            row = session.run(
                "MATCH (s:Story {story_id: $story_id}) "
                "OPTIONAL MATCH (s)-[m:MENTIONS]->() "
                "WITH s, count(DISTINCT m) AS mentions "
                "OPTIONAL MATCH (s)-[h:HAS_THEME]->() "
                "WITH s, mentions, count(DISTINCT h) AS themes "
                "OPTIONAL MATCH (s)-[p:NEAR_IN_SIGNIFIER_SPACE]-() "
                "RETURN count(DISTINCT s) AS stories, mentions, themes, "
                "count(DISTINCT p) AS proximity",
                story_id=target_id,
            ).single()
        return row["stories"], row["mentions"], row["themes"], row["proximity"]

    before_replay = cardinalities()
    assert before_replay == (1, 1, 1, 1)

    queue.enqueue(target_id)
    worker.run_once()
    replayed = storage.get_story(target_id)

    assert (replayed.entities, replayed.themes, replayed.sentiment) == enrichment
    assert replayed.processing_attempts == 3
    assert replayed.processing_status == "processed"
    assert replayed.next_processing_at is None
    assert replayed.processing_error is None
    assert (llm.entity_calls, llm.theme_calls, llm.sentiment_calls) == (1, 1, 1)
    assert cardinalities() == before_replay
