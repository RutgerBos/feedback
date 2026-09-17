"""
Background worker entrypoint.

Run with:
    uv run python -m src.workers.run_worker

The worker:
1. Connects to Redis and MongoDB/Neo4j using Settings
2. Runs a main loop: dequeue + process, with periodic sweeps
"""

import logging
import signal
import time
from dataclasses import dataclass
from threading import Event
from typing import Any

import neo4j
import redis as redis_lib
from pymongo import MongoClient

from src.adapters.llm_factory import create_llm_provider
from src.adapters.mongodb_storage import MongoDBStorageAdapter
from src.adapters.neo4j_graph import Neo4jGraphAdapter
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


@dataclass
class WorkerRuntime:
    """
    Responsibilities:
    - Own the active worker and its process-scoped resources
    - Release worker resources during shutdown

    Collaborators:
    - StoryWorker
    """

    worker: StoryWorker
    mongo_client: Any
    neo4j_driver: Any
    redis_client: Any

    def close(self) -> None:
        """Best-effort cleanup; one failed close must not skip the others."""
        for name, client in (
            ("redis", self.redis_client),
            ("neo4j", self.neo4j_driver),
            ("mongodb", self.mongo_client),
        ):
            try:
                client.close()
            except Exception:
                logger.exception("Failed to close %s client", name)


def build_runtime(settings: Settings) -> WorkerRuntime:
    """Wire all dependencies and retain their clients for shutdown."""
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_url)
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
    })

    proximity = ProximityCalculationService(storage=storage, graph=graph, threshold=settings.proximity_threshold)
    graph_projection = GraphProjectionService(storage=storage, graph=graph, proximity=proximity)
    entity_service = EntityExtractionService(
        storage=storage,
        llm=llm,
        graph_projection=graph_projection,
    )
    sentiment_service = SentimentExtractionService(storage=storage, llm=llm)
    processing_service = StoryProcessingService(
        storage=storage,
        graph=graph,
        entity_service=entity_service,
        sentiment_service=sentiment_service,
    )

    redis_client = redis_lib.from_url(settings.redis_url)
    queue = WorkerQueue(
        redis=redis_client,
        queue_key=settings.worker_queue_key,
        visibility_timeout=settings.worker_visibility_timeout,
    )

    worker = StoryWorker(
        queue=queue,
        processing_service=processing_service,
        storage=storage,
        dequeue_timeout=settings.worker_dequeue_timeout,
        max_attempts=settings.worker_max_attempts,
        retry_base_delay=settings.worker_retry_base_delay,
    )
    return WorkerRuntime(
        worker=worker,
        mongo_client=mongo_client,
        neo4j_driver=neo4j_driver,
        redis_client=redis_client,
    )


def _run_loop(runtime: WorkerRuntime, settings: Settings, stop_event: Event) -> None:
    """Process queued work until a termination signal requests shutdown."""
    worker = runtime.worker
    sweep_interval = settings.worker_sweep_interval
    logger.info("Worker started. Queue: %s, sweep every %ds", settings.worker_queue_key, sweep_interval)

    last_sweep = 0.0
    while not stop_event.is_set():
        now = time.monotonic()
        if now - last_sweep >= sweep_interval:
            logger.info("Running periodic sweep")
            worker.sweep()
            last_sweep = now

        worker.run_once()


def main() -> None:
    settings = Settings()
    runtime = build_runtime(settings)
    stop_event = Event()

    def request_shutdown(signum: int, frame: Any) -> None:
        logger.info("Received signal %s; shutting down worker", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    try:
        _run_loop(runtime, settings, stop_event)
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
