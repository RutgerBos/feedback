"""MongoDB + Redis integration path from submission through worker completion."""

from unittest.mock import Mock

import pytest
import redis as redis_lib
from pymongo import MongoClient

from src.adapters.mongodb_storage import MongoDBStorageAdapter
from src.domain.models import SentimentAnalysis
from src.ports.llm import EntityExtraction
from src.services.entity_extraction import EntityExtractionService
from src.services.sentiment_extraction import SentimentExtractionService
from src.services.story_processing import StoryProcessingService
from src.services.story_submission import (
    SignificationRequest,
    StorySubmissionRequest,
    StorySubmissionService,
    TriadResponseRequest,
)
from src.workers.story_worker import StoryWorker
from src.workers.worker_queue import WorkerQueue


class SuccessfulLLM:
    def extract_entities(self, story_text: str) -> EntityExtraction:
        return EntityExtraction(entities=[{"name": "CI", "type": "tool"}])

    def extract_themes(self, story_text: str) -> list[str]:
        return ["delivery friction"]

    def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
        return SentimentAnalysis(
            emotion_markers=["frustration"],
            process_sentiment="negative",
            outcome_sentiment="neutral",
        )


@pytest.fixture
def worker_db():
    client = MongoClient("mongodb://admin:password@localhost:27017/")
    db = client["test_feedback_worker_pipeline"]
    db.stories.delete_many({})
    yield db
    db.stories.delete_many({})
    client.close()


@pytest.fixture
def redis_client():
    client = redis_lib.Redis.from_url(
        "redis://localhost:6379/0",
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        client.ping()
    except redis_lib.RedisError:
        pytest.skip("Redis not reachable at localhost:6379")
    yield client
    client.close()


@pytest.mark.asyncio
async def test_submission_is_processed_by_redis_worker(worker_db, redis_client):
    from src.api.stories import submit_story

    storage = MongoDBStorageAdapter(worker_db)
    queue_key = "test:feedback:worker-pipeline"
    redis_client.delete(queue_key)
    queue = WorkerQueue(redis=redis_client, queue_key=queue_key)
    submission_service = StorySubmissionService(
        storage=storage,
        valid_triad_ids={"workflow_nature"},
    )
    graph = Mock()
    llm = SuccessfulLLM()
    processing_service = StoryProcessingService(
        storage=storage,
        graph=graph,
        entity_service=EntityExtractionService(storage=storage, llm=llm),  # type: ignore[arg-type]
        sentiment_service=SentimentExtractionService(storage=storage, llm=llm),  # type: ignore[arg-type]
    )
    worker = StoryWorker(
        queue=queue,
        processing_service=processing_service,
        storage=storage,
        dequeue_timeout=0,
    )
    request = StorySubmissionRequest(
        story_text="The delivery pipeline failed repeatedly and delayed our release for several days.",
        signification=SignificationRequest(
            responses=[
                TriadResponseRequest(
                    signifier_id="workflow_nature",
                    coordinates={"x": 0.3, "y": 0.6},
                )
            ]
        ),
    )

    result = await submit_story(request=request, service=submission_service, queue=queue)
    assert storage.get_story(result.story_id).processing_status == "pending"

    worker.run_once()

    story = storage.get_story(result.story_id)
    assert story.processing_status == "processed"
    assert story.entity_status == "processed"
    assert story.sentiment_status == "processed"
    assert story.processing_attempts == 1
    assert story.entities == [{"name": "CI", "type": "tool"}]
    redis_client.delete(queue_key)
