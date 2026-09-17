"""Unit tests for StoryWorker."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace


class FakeQueue:
    """Fake WorkerQueue: dequeue returns items from a pre-loaded list."""

    def __init__(self, story_ids: list[str], fail_complete: bool = False):
        self._ids = list(story_ids)
        self.enqueued: list[str] = []
        self.completed: list[str] = []
        self.dequeue_timeouts: list[int] = []
        self._fail_complete = fail_complete

    def dequeue(self, timeout=5) -> str | None:
        self.dequeue_timeouts.append(timeout)
        return self._ids.pop(0) if self._ids else None

    def enqueue(self, story_id: str) -> None:
        self.enqueued.append(story_id)

    def complete(self, story_id: str) -> None:
        if self._fail_complete:
            raise ConnectionError("redis unavailable")
        self.completed.append(story_id)


class FakeProcessingService:
    """Fake StoryProcessingService: records calls."""

    def __init__(
        self,
        fail_on: set[str] | None = None,
        incomplete_on: set[str] | None = None,
    ):
        self.processed: list[str] = []
        self._fail_on = fail_on or set()
        self._incomplete_on = incomplete_on or set()

    def process(self, story_id: str) -> bool:
        if story_id in self._fail_on:
            raise RuntimeError(f"processing failed for {story_id}")
        self.processed.append(story_id)
        return story_id not in self._incomplete_on


class FakeSweepStorage:
    """Fake StoragePort subset: only find_story_ids_requiring_processing."""

    def __init__(self, pending: list[str], attempts: dict[str, int] | None = None):
        self._pending = list(pending)
        self._attempts = attempts or {}
        self.processing_updates: list[dict[str, object]] = []

    def find_story_ids_requiring_processing(self) -> list[str]:
        return list(self._pending)

    def get_story(self, story_id: str):
        return SimpleNamespace(processing_attempts=self._attempts.get(story_id, 0))

    def update_story_processing(self, story_id: str, **state: object) -> None:
        self.processing_updates.append({"story_id": story_id, **state})


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_run_once_processes_story_from_queue():
    """run_once() dequeues a story_id and calls processing service."""
    from src.workers.story_worker import StoryWorker

    queue = FakeQueue(["story-abc"])
    service = FakeProcessingService()
    storage = FakeSweepStorage([])

    worker = StoryWorker(queue=queue, processing_service=service, storage=storage)
    worker.run_once()

    assert "story-abc" in service.processed
    assert queue.completed == ["story-abc"]
    assert storage.processing_updates == [{
        "story_id": "story-abc",
        "processing_status": "processed",
        "processing_attempts": 1,
        "next_processing_at": None,
        "processing_error": None,
    }]


def test_run_once_does_nothing_when_queue_empty():
    """run_once() is a no-op when the queue returns None."""
    from src.workers.story_worker import StoryWorker

    queue = FakeQueue([])
    service = FakeProcessingService()

    worker = StoryWorker(queue=queue, processing_service=service, storage=FakeSweepStorage([]))
    worker.run_once()

    assert service.processed == []


def test_run_once_does_not_crash_on_processing_error():
    """run_once() swallows processing errors and does not re-raise."""
    from src.workers.story_worker import StoryWorker

    queue = FakeQueue(["story-bad"])
    service = FakeProcessingService(fail_on={"story-bad"})

    worker = StoryWorker(queue=queue, processing_service=service, storage=FakeSweepStorage([]))
    worker.run_once()  # should not raise

    assert queue.completed == ["story-bad"]


def test_sweep_enqueues_pending_stories():
    """sweep() finds unprocessed stories in storage and enqueues them."""
    from src.workers.story_worker import StoryWorker

    queue = FakeQueue([])
    service = FakeProcessingService()
    storage = FakeSweepStorage(["story-x", "story-y"])

    worker = StoryWorker(queue=queue, processing_service=service, storage=storage)
    worker.sweep()

    assert "story-x" in queue.enqueued
    assert "story-y" in queue.enqueued


def test_sweep_enqueues_nothing_when_all_processed():
    """sweep() does not enqueue anything when no stories require processing."""
    from src.workers.story_worker import StoryWorker

    queue = FakeQueue([])
    service = FakeProcessingService()
    storage = FakeSweepStorage([])

    worker = StoryWorker(queue=queue, processing_service=service, storage=storage)
    worker.sweep()

    assert queue.enqueued == []


def test_run_once_uses_configured_dequeue_timeout():
    from src.workers.story_worker import StoryWorker

    queue = FakeQueue([])
    worker = StoryWorker(
        queue=queue,
        processing_service=FakeProcessingService(),
        storage=FakeSweepStorage([]),
        dequeue_timeout=17,
    )

    worker.run_once()

    assert queue.dequeue_timeouts == [17]


def test_processing_failure_is_scheduled_with_exponential_backoff():
    from src.workers.story_worker import StoryWorker

    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    queue = FakeQueue(["story-bad"])
    storage = FakeSweepStorage([], attempts={"story-bad": 1})
    worker = StoryWorker(
        queue=queue,
        processing_service=FakeProcessingService(fail_on={"story-bad"}),
        storage=storage,
        max_attempts=3,
        retry_base_delay=30,
        clock=lambda: now,
    )

    worker.run_once()

    assert storage.processing_updates == [{
        "story_id": "story-bad",
        "processing_status": "retrying",
        "processing_attempts": 2,
        "next_processing_at": now + timedelta(seconds=60),
        "processing_error": "processing failed for story-bad",
    }]


def test_processing_stops_after_maximum_attempts():
    from src.workers.story_worker import StoryWorker

    queue = FakeQueue(["story-bad"])
    storage = FakeSweepStorage([], attempts={"story-bad": 2})
    worker = StoryWorker(
        queue=queue,
        processing_service=FakeProcessingService(fail_on={"story-bad"}),
        storage=storage,
        max_attempts=3,
    )

    worker.run_once()

    assert storage.processing_updates[0]["processing_status"] == "failed"
    assert storage.processing_updates[0]["processing_attempts"] == 3
    assert storage.processing_updates[0]["next_processing_at"] is None


def test_partial_llm_failure_is_treated_as_failed_attempt():
    from src.workers.story_worker import StoryWorker

    queue = FakeQueue(["story-partial"])
    storage = FakeSweepStorage([])
    worker = StoryWorker(
        queue=queue,
        processing_service=FakeProcessingService(incomplete_on={"story-partial"}),
        storage=storage,
    )

    worker.run_once()

    assert storage.processing_updates[0]["processing_status"] == "retrying"


def test_acknowledgement_failure_does_not_crash_worker():
    from src.workers.story_worker import StoryWorker

    worker = StoryWorker(
        queue=FakeQueue(["story-abc"], fail_complete=True),
        processing_service=FakeProcessingService(),
        storage=FakeSweepStorage([]),
    )

    worker.run_once()  # visibility timeout makes this recoverable; loop stays alive
