"""StoryWorker: dequeues story IDs and triggers processing."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class StoryWorker:
    """
    Responsibilities:
    - Dequeue story IDs from the queue and process them
    - Sweep storage for unprocessed stories and enqueue them
    - Swallow processing errors so the loop does not crash

    Collaborators:
    - WorkerQueue (dequeue/enqueue)
    - StoryProcessingService (process)
    - StoragePort subset (find_story_ids_requiring_processing)

    Notes:
    - run_once() handles exactly one dequeue cycle
    - sweep() enqueues all currently unprocessed stories
    - Caller (main loop) controls timing between run_once/sweep calls
    """

    def __init__(
        self,
        queue: Any,
        processing_service: Any,
        storage: Any,
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
        try:
            story = self._storage.get_story(story_id)
            attempt = story.processing_attempts + 1
            try:
                completed = self._service.process(story_id)
                if completed is False:
                    raise RuntimeError("Story enrichment did not complete")
                self._storage.update_story_processing(
                    story_id,
                    processing_status="processed",
                    processing_attempts=attempt,
                    next_processing_at=None,
                    processing_error=None,
                )
            except Exception as error:
                logger.exception("Failed to process story %s", story_id)
                terminal = attempt >= self._max_attempts
                delay = self._retry_base_delay * (2 ** (attempt - 1))
                self._storage.update_story_processing(
                    story_id,
                    processing_status="failed" if terminal else "retrying",
                    processing_attempts=attempt,
                    next_processing_at=(
                        None if terminal else self._clock() + timedelta(seconds=delay)
                    ),
                    processing_error=str(error),
                )
        except Exception:
            logger.exception("Failed to persist processing state for story %s", story_id)
        finally:
            try:
                self._queue.complete(story_id)
            except Exception:
                logger.exception("Failed to acknowledge story %s", story_id)

    def sweep(self) -> None:
        """Enqueue all stories that still require processing."""
        pending = self._storage.find_story_ids_requiring_processing()
        for story_id in pending:
            self._queue.enqueue(story_id)
