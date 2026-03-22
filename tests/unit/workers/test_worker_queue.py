"""Unit tests for WorkerQueue."""

import pytest


class FakeRedis:
    """Minimal Redis fake: supports lpush, brpop, llen."""

    def __init__(self):
        self._lists: dict[str, list[bytes]] = {}

    def lpush(self, key: str, *values) -> int:
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
