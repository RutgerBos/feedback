"""Unit tests for WorkerQueue."""

import pytest


class FakeRedis:
    """Minimal Redis fake for the queue's list and membership set."""

    def __init__(self):
        self._lists: dict[str, list[bytes]] = {}
        self._values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}
        self.fail_lpush = False

    def lpush(self, key: str, *values) -> int:
        if self.fail_lpush:
            raise ConnectionError("redis write failed")
        self._lists.setdefault(key, [])
        for v in reversed(values):
            self._lists[key].insert(0, v if isinstance(v, bytes) else v.encode())
        return len(self._lists[key])

    def brpop(self, keys, timeout=0):
        if isinstance(keys, str):
            keys = [keys]
        for key in keys:
            items = self._lists.get(key, [])
            if items:
                return (key.encode() if isinstance(key, str) else key, items.pop())
        return None

    def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        if nx and key in self._values:
            return False
        self._values[key] = value
        self.expirations[key] = ex
        return True

    def delete(self, key: str) -> int:
        existed = key in self._values
        self._values.pop(key, None)
        self.expirations.pop(key, None)
        return int(existed)


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_enqueue_pushes_story_id_to_redis():
    """enqueue() pushes story_id onto the configured queue key."""
    from src.workers.worker_queue import WorkerQueue

    redis = FakeRedis()
    q = WorkerQueue(redis=redis, queue_key="test:queue")

    q.enqueue("story-abc")

    assert redis.llen("test:queue") == 1


def test_dequeue_returns_story_id():
    """dequeue() pops and returns a story_id string."""
    from src.workers.worker_queue import WorkerQueue

    redis = FakeRedis()
    q = WorkerQueue(redis=redis, queue_key="test:queue")
    q.enqueue("story-abc")

    result = q.dequeue(timeout=0)

    assert result == "story-abc"


def test_dequeue_returns_none_when_empty():
    """dequeue() returns None when the queue is empty (timeout expired)."""
    from src.workers.worker_queue import WorkerQueue

    redis = FakeRedis()
    q = WorkerQueue(redis=redis, queue_key="test:queue")

    result = q.dequeue(timeout=0)

    assert result is None


def test_enqueue_multiple_preserves_fifo_order():
    """Stories are dequeued in the order they were enqueued."""
    from src.workers.worker_queue import WorkerQueue

    redis = FakeRedis()
    q = WorkerQueue(redis=redis, queue_key="test:queue")

    q.enqueue("first")
    q.enqueue("second")
    q.enqueue("third")

    assert q.dequeue(timeout=0) == "first"
    assert q.dequeue(timeout=0) == "second"
    assert q.dequeue(timeout=0) == "third"


def test_enqueue_ignores_story_already_outstanding():
    from src.workers.worker_queue import WorkerQueue

    redis = FakeRedis()
    q = WorkerQueue(redis=redis, queue_key="test:queue")

    q.enqueue("story-abc")
    q.enqueue("story-abc")

    assert redis.llen("test:queue") == 1


def test_completed_story_can_be_enqueued_again():
    from src.workers.worker_queue import WorkerQueue

    redis = FakeRedis()
    q = WorkerQueue(redis=redis, queue_key="test:queue")
    q.enqueue("story-abc")
    assert q.dequeue(timeout=0) == "story-abc"

    q.complete("story-abc")
    q.enqueue("story-abc")

    assert q.dequeue(timeout=0) == "story-abc"


def test_outstanding_marker_has_crash_recovery_timeout():
    from src.workers.worker_queue import WorkerQueue

    redis = FakeRedis()
    q = WorkerQueue(redis=redis, queue_key="test:queue", visibility_timeout=123)

    q.enqueue("story-abc")

    assert redis.expirations["test:queue:outstanding:story-abc"] == 123


def test_enqueue_failure_releases_outstanding_marker():
    from src.workers.worker_queue import WorkerQueue

    redis = FakeRedis()
    redis.fail_lpush = True
    q = WorkerQueue(redis=redis, queue_key="test:queue")

    with pytest.raises(ConnectionError, match="redis write failed"):
        q.enqueue("story-abc")

    redis.fail_lpush = False
    q.enqueue("story-abc")
    assert redis.llen("test:queue") == 1
