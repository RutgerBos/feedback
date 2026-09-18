"""StoryWorker: dequeues story IDs and triggers processing."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from src.ports.storage import StoragePort


class StoryQueue(Protocol):
    """
    Responsibilities:
    - Coordinate durable delivery and acknowledgement of story work

    Collaborators:
    - None
    """

    def enqueue(self, story_id: str) -> None: ...

    def dequeue(self, timeout: int = 5) -> str | None: ...

    def complete(self, story_id: str) -> None: ...


class StoryProcessor(Protocol):
    """
    Responsibilities:
    - Enrich a story through the processing pipeline

    Collaborators:
    - None
    """

    def process(self, story_id: str) -> bool | None: ...

logger = logging.getLogger(__name__)


class StoryWorker:
    """
    Responsibilities:
    - Consume and coordinate queued story-processing work
    - Recover unqueued stories that still require processing
    - Keep processing available when individual work items fail

    Collaborators:
    - StoryQueue
    - StoryProcessor
    - StoragePort
    """

    def __init__(
        self,
        queue: StoryQueue,
        processing_service: StoryProcessor,
        storage: StoragePort,
        dequeue_timeout: int = 5,
        max_attempts: int = 3,
        retry_base_delay: int = 30,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._queue = queue
        self._service = processing_service
        self._storage = storage
        self._dequeue_timeout = dequeue_timeout
        self._max_attempts = max_attempts
        self._retry_base_delay = retry_base_delay
        self._clock = clock or (lambda: datetime.now(UTC))

    def run_once(self) -> None:
        """Dequeue one story and process it; silently skip errors."""
        story_id = self._queue.dequeue(timeout=self._dequeue_timeout)
        if story_id is None:
            return
        state_persisted = False
        try:
            story = self._storage.get_story(story_id)
            attempt = story.processing_attempts + 1
            try:
                completed = self._service.process(story_id)
                if completed is False:
                    raise RuntimeError("Story enrichment did not complete")
                processing_status = "processed"
                next_processing_at = None
                processing_error = None
            except Exception as error:
                logger.exception("Failed to process story %s", story_id)
                terminal = attempt >= self._max_attempts
                delay = self._retry_base_delay * (2 ** (attempt - 1))
                processing_status = "failed" if terminal else "retrying"
                next_processing_at = (
                    None if terminal else self._clock() + timedelta(seconds=delay)
                )
                processing_error = str(error)
            self._storage.update_story_processing(
                story_id,
                processing_status=processing_status,
                processing_attempts=attempt,
                next_processing_at=next_processing_at,
                processing_error=processing_error,
            )
            state_persisted = True
        except Exception:
            logger.exception("Failed to persist processing state for story %s", story_id)
        if state_persisted:
            try:
                self._queue.complete(story_id)
            except Exception:
                logger.exception("Failed to acknowledge story %s", story_id)

    def sweep(self) -> None:
        """Enqueue all stories that still require processing."""
        pending = self._storage.find_story_ids_requiring_processing()
        for story_id in pending:
            self._queue.enqueue(story_id)
