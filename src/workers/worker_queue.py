"""WorkerQueue: thin Redis wrapper for story-processing task queue."""


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

    def __init__(self, redis, queue_key: str) -> None:
        self._redis = redis
        self._queue_key = queue_key

    def enqueue(self, story_id: str) -> None:
        self._redis.lpush(self._queue_key, story_id)

    def dequeue(self, timeout: int = 5) -> str | None:
        result = self._redis.brpop(self._queue_key, timeout=timeout)
        if result is None:
            return None
        _key, value = result
        return value.decode() if isinstance(value, bytes) else value
