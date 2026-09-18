"""Application composition root for API and worker processes."""

import logging
from dataclasses import dataclass
from typing import Any, Protocol, cast

import neo4j
import redis as redis_lib
from fastapi import Depends, FastAPI, Request
from pymongo import MongoClient

from src.adapters.llm_factory import create_llm_provider
from src.adapters.mongodb_storage import MongoDBStorageAdapter
from src.adapters.neo4j_graph import Neo4jGraphAdapter
from src.config.settings import Settings
from src.ports.graph import GraphPort
from src.ports.llm import LLMPort
from src.ports.storage import StoragePort
from src.services.anomaly_detection import AnomalyDetectionService
from src.services.clustering import ClusteringService
from src.services.dashboard import DashboardService
from src.services.entity_extraction import EntityExtractionService
from src.services.graph_projection import GraphProjectionService
from src.services.insight_synthesis import InsightSynthesisService
from src.services.nl_query import NLQueryService
from src.services.pattern_query import PatternQueryService
from src.services.proximity import ProximityCalculationService
from src.services.sentiment_extraction import SentimentExtractionService
from src.services.story_processing import StoryProcessingService
from src.services.story_submission import StorySubmissionService
from src.services.temporal import TemporalService
from src.workers.story_worker import StoryWorker
from src.workers.worker_queue import WorkerQueue


class LLMSettings(Protocol):
    """
    <crc>
    responsibilities:
      - Expose the configuration required to select an LLM provider
    collaborators: []
    </crc>
    """

    llm_provider: str
    llm_model: str
    local_model_url: str


def create_configured_llm(settings: LLMSettings) -> LLMPort:
    """Create the configured process-scoped LLM adapter."""
    return create_llm_provider(
        {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "base_url": settings.local_model_url,
        }
    )


def get_storage(request: Request) -> StoragePort:
    """Provide MongoDB storage from process-scoped application resources."""
    client = request.app.state.mongo_client
    database = request.app.state.settings.mongodb_database
    return MongoDBStorageAdapter(client[database])


def get_graph(request: Request) -> GraphPort:
    """Provide the graph adapter from the process-scoped Neo4j driver."""
    return Neo4jGraphAdapter(driver=request.app.state.neo4j_driver)


def get_llm(request: Request) -> LLMPort:
    """Provide the process-scoped LLM adapter."""
    return cast(LLMPort, request.app.state.llm)


def get_queue(request: Request) -> WorkerQueue:
    """Provide the process-scoped worker queue."""
    return cast(WorkerQueue, request.app.state.worker_queue)


def get_proximity_service(
    request: Request,
    storage: StoragePort = Depends(get_storage),
    graph: GraphPort = Depends(get_graph),
) -> ProximityCalculationService:
    threshold = request.app.state.settings.proximity_threshold
    return ProximityCalculationService(storage=storage, graph=graph, threshold=threshold)


def get_graph_projection_service(
    storage: StoragePort = Depends(get_storage),
    graph: GraphPort = Depends(get_graph),
    proximity: ProximityCalculationService = Depends(get_proximity_service),
) -> GraphProjectionService:
    return GraphProjectionService(storage=storage, graph=graph, proximity=proximity)


def get_entity_extraction_service(
    storage: StoragePort = Depends(get_storage),
    llm: LLMPort = Depends(get_llm),
    graph_projection: GraphProjectionService = Depends(get_graph_projection_service),
) -> EntityExtractionService:
    return EntityExtractionService(storage=storage, llm=llm, graph_projection=graph_projection)


def get_sentiment_extraction_service(
    storage: StoragePort = Depends(get_storage),
    llm: LLMPort = Depends(get_llm),
) -> SentimentExtractionService:
    return SentimentExtractionService(storage=storage, llm=llm)


def get_submission_service(
    request: Request,
    storage: StoragePort = Depends(get_storage),
) -> StorySubmissionService:
    triad_config = getattr(request.app.state, "triad_config", None)
    valid_triad_ids = {triad.id for triad in triad_config.triads} if triad_config else None
    return StorySubmissionService(storage, valid_triad_ids=valid_triad_ids)


def get_pattern_query_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
) -> PatternQueryService:
    return PatternQueryService(graph=graph, storage=storage)


def get_clustering_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
) -> ClusteringService:
    return ClusteringService(graph=graph, storage=storage)


def get_temporal_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
) -> TemporalService:
    return TemporalService(graph=graph, storage=storage)


def get_anomaly_detection_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
) -> AnomalyDetectionService:
    return AnomalyDetectionService(graph=graph, storage=storage)


def get_insight_synthesis_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
    llm: LLMPort = Depends(get_llm),
) -> InsightSynthesisService:
    return InsightSynthesisService(graph=graph, storage=storage, llm=llm)


def get_nl_query_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
    llm: LLMPort = Depends(get_llm),
) -> NLQueryService:
    return NLQueryService(graph=graph, storage=storage, llm=llm)


def get_dashboard_service(
    storage: StoragePort = Depends(get_storage),
) -> DashboardService:
    return DashboardService(storage=storage)


@dataclass
class ApiRuntime:
    """
    <crc>
    responsibilities:
      - Retain API-process resources for request handling and orderly shutdown
      - Publish process-scoped dependencies to the application
      - Release all process resources even when one cleanup fails
    collaborators: []
    </crc>
    """

    llm: LLMPort
    mongo_client: Any
    neo4j_driver: Any
    redis_client: Any
    worker_queue: WorkerQueue

    def install(self, app: FastAPI, settings: Settings) -> None:
        """Publish process-scoped resources for FastAPI dependencies."""
        app.state.settings = settings
        app.state.llm = self.llm
        app.state.mongo_client = self.mongo_client
        app.state.neo4j_driver = self.neo4j_driver
        app.state.worker_queue = self.worker_queue

    def close(self) -> None:
        """Release every owned client even when an earlier close fails."""
        _close_resources(
            ("redis", self.redis_client),
            ("neo4j", self.neo4j_driver),
            ("mongodb", self.mongo_client),
        )


@dataclass
class WorkerRuntime:
    """
    <crc>
    responsibilities:
      - Retain worker-process resources for orderly shutdown
      - Release all process resources even when one cleanup fails
    collaborators: []
    </crc>
    """

    worker: StoryWorker
    mongo_client: Any
    neo4j_driver: Any
    redis_client: Any

    def close(self) -> None:
        """Best-effort cleanup; one failed close must not skip the others."""
        _close_resources(
            ("redis", self.redis_client),
            ("neo4j", self.neo4j_driver),
            ("mongodb", self.mongo_client),
        )


def _close_resources(*resources: tuple[str, Any]) -> None:
    """Best-effort close of independently owned process resources."""
    logger = logging.getLogger(__name__)
    for name, client in resources:
        try:
            client.close()
        except Exception:
            logger.exception("Failed to close %s client", name)


def build_api_runtime(settings: Settings) -> ApiRuntime:
    """Construct all process-scoped resources used by the API."""
    llm = create_configured_llm(settings)
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_url)
    neo4j_driver = neo4j.GraphDatabase.driver(
        settings.neo4j_url,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    redis_client = redis_lib.from_url(settings.redis_url)
    worker_queue = WorkerQueue(
        redis=redis_client,
        queue_key=settings.worker_queue_key,
        visibility_timeout=settings.worker_visibility_timeout,
    )
    return ApiRuntime(
        llm=llm,
        mongo_client=mongo_client,
        neo4j_driver=neo4j_driver,
        redis_client=redis_client,
        worker_queue=worker_queue,
    )


def build_worker_runtime(settings: Settings) -> WorkerRuntime:
    """Wire the worker and retain its process-scoped resources for shutdown."""
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_url)
    storage = MongoDBStorageAdapter(mongo_client[settings.mongodb_database])
    neo4j_driver = neo4j.GraphDatabase.driver(
        settings.neo4j_url,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    graph = Neo4jGraphAdapter(driver=neo4j_driver)
    llm = create_configured_llm(settings)
    proximity = ProximityCalculationService(
        storage=storage,
        graph=graph,
        threshold=settings.proximity_threshold,
    )
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
