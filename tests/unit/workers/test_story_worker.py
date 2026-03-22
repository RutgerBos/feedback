"""Unit tests for StoryWorker."""

import pytest


class FakeQueue:
    """Fake WorkerQueue: dequeue returns items from a pre-loaded list."""

    def __init__(self, story_ids: list[str]):
        self._ids = list(story_ids)
        self.enqueued: list[str] = []

    def dequeue(self, timeout=5) -> str | None:
        return self._ids.pop(0) if self._ids else None

    def enqueue(self, story_id: str) -> None:
        self.enqueued.append(story_id)


class FakeProcessingService:
    """Fake StoryProcessingService: records calls."""

    def __init__(self, fail_on: set[str] | None = None):
        self.processed: list[str] = []
        self._fail_on = fail_on or set()

    def process(self, story_id: str) -> None:
        if story_id in self._fail_on:
            raise RuntimeError(f"processing failed for {story_id}")
        self.processed.append(story_id)


class FakeSweepStorage:
    """Fake StoragePort subset: only find_story_ids_requiring_processing."""

    def __init__(self, pending: list[str]):
        self._pending = list(pending)

    def find_story_ids_requiring_processing(self) -> list[str]:
        return list(self._pending)


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_run_once_processes_story_from_queue():
    """run_once() dequeues a story_id and calls processing service."""
    from src.workers.story_worker import StoryWorker

    queue = FakeQueue(["story-abc"])
    service = FakeProcessingService()

    worker = StoryWorker(queue=queue, processing_service=service, storage=FakeSweepStorage([]))
    worker.run_once()

    assert "story-abc" in service.processed


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
