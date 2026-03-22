"""
Background worker entrypoint.

Run with:
    uv run python -m src.workers.run_worker

The worker:
1. Connects to Redis and MongoDB/Neo4j using Settings
2. Runs a main loop: dequeue + process, with periodic sweeps
"""

import logging
import time

import redis as redis_lib
import neo4j
from pymongo import MongoClient

from src.adapters.mongodb_storage import MongoDBStorageAdapter
from src.adapters.neo4j_graph import Neo4jGraphAdapter
from src.adapters.llm_factory import create_llm_provider
from src.config.settings import Settings
from src.services.entity_extraction import EntityExtractionService
from src.services.graph_projection import GraphProjectionService
from src.services.proximity import ProximityCalculationService
from src.services.sentiment_extraction import SentimentExtractionService
from src.services.story_processing import StoryProcessingService
from src.workers.story_worker import StoryWorker
from src.workers.worker_queue import WorkerQueue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def build_worker(settings: Settings) -> StoryWorker:
    """Wire up all dependencies and return a ready StoryWorker."""
    mongo_client = MongoClient(settings.mongodb_url)
    db = mongo_client[settings.mongodb_database]
    storage = MongoDBStorageAdapter(db)

    neo4j_driver = neo4j.GraphDatabase.driver(
        settings.neo4j_url,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    graph = Neo4jGraphAdapter(driver=neo4j_driver)

    llm = create_llm_provider({
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "base_url": settings.local_model_url,
    }) if settings.llm_provider != "none" else None

    proximity = ProximityCalculationService(storage=storage, graph=graph, threshold=settings.proximity_threshold)
    graph_projection = GraphProjectionService(storage=storage, graph=graph, proximity=proximity)
    entity_service = EntityExtractionService(storage=storage, llm=llm, graph_projection=graph_projection)  # type: ignore[arg-type]
    sentiment_service = SentimentExtractionService(storage=storage, llm=llm)  # type: ignore[arg-type]
    processing_service = StoryProcessingService(
        storage=storage,
        graph=graph,
        entity_service=entity_service,
        sentiment_service=sentiment_service,
    )

    redis_client = redis_lib.from_url(settings.redis_url)
    queue = WorkerQueue(redis=redis_client, queue_key=settings.worker_queue_key)

    return StoryWorker(queue=queue, processing_service=processing_service, storage=storage)


def main() -> None:
    settings = Settings()
    worker = build_worker(settings)
    sweep_interval = settings.worker_sweep_interval

    logger.info("Worker started. Queue: %s, sweep every %ds", settings.worker_queue_key, sweep_interval)

    last_sweep = 0.0
    while True:
        now = time.monotonic()
        if now - last_sweep >= sweep_interval:
            logger.info("Running periodic sweep")
            worker.sweep()
            last_sweep = now

        worker.run_once()


if __name__ == "__main__":
    main()
