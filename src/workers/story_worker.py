"""StoryWorker: dequeues story IDs and triggers processing."""

import logging

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

    def __init__(self, queue, processing_service, storage) -> None:
        self._queue = queue
        self._service = processing_service
        self._storage = storage

    def run_once(self) -> None:
        """Dequeue one story and process it; silently skip errors."""
        story_id = self._queue.dequeue()
        if story_id is None:
            return
        try:
            self._service.process(story_id)
        except Exception:
            logger.exception("Failed to process story %s", story_id)

    def sweep(self) -> None:
        """Enqueue all stories that still require processing."""
        pending = self._storage.find_story_ids_requiring_processing()
        for story_id in pending:
            self._queue.enqueue(story_id)
