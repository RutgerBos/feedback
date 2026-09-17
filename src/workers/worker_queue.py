"""WorkerQueue: Redis-backed story-processing queue with deduplication."""

from typing import Any


class WorkerQueue:
    """
    Responsibilities:
    - Enqueue story IDs for background processing
    - Dequeue story IDs for the worker to consume

    Collaborators:
    - Redis client (injected)

    Notes:
    - Uses lpush/brpop to implement FIFO semantics
    - queue_key is configurable so tests can use isolated keys
    """

    def __init__(self, redis: Any, queue_key: str, visibility_timeout: int = 3600) -> None:
        self._redis = redis
        self._queue_key = queue_key
        self._visibility_timeout = visibility_timeout

    def _outstanding_key(self, story_id: str) -> str:
        return f"{self._queue_key}:outstanding:{story_id}"

    def enqueue(self, story_id: str) -> None:
        marker_key = self._outstanding_key(story_id)
        if not self._redis.set(
            marker_key,
            "1",
            nx=True,
            ex=self._visibility_timeout,
        ):
            return
        try:
            self._redis.lpush(self._queue_key, story_id)
        except Exception:
            self._redis.delete(marker_key)
            raise

    def dequeue(self, timeout: int = 5) -> str | None:
        result = self._redis.brpop(self._queue_key, timeout=timeout)
        if result is None:
            return None
        _key, value = result
        return value.decode() if isinstance(value, bytes) else value

    def complete(self, story_id: str) -> None:
        """Release a story's outstanding marker after an attempt finishes."""
        self._redis.delete(self._outstanding_key(story_id))
