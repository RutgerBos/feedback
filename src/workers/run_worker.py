"""
Background worker entrypoint.

Run with:
    uv run python -m src.workers.run_worker

The worker:
1. Connects to Redis and MongoDB/Neo4j using Settings
2. Runs a main loop: dequeue + process, with periodic sweeps
"""

import logging
import signal
import time
from threading import Event
from typing import Any

from src.composition import WorkerRuntime
from src.composition import build_worker_runtime as build_runtime
from src.config.settings import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _run_loop(runtime: WorkerRuntime, settings: Settings, stop_event: Event) -> None:
    """Process queued work until a termination signal requests shutdown."""
    worker = runtime.worker
    sweep_interval = settings.worker_sweep_interval
    logger.info("Worker started. Queue: %s, sweep every %ds", settings.worker_queue_key, sweep_interval)

    last_sweep = 0.0
    while not stop_event.is_set():
        now = time.monotonic()
        if now - last_sweep >= sweep_interval:
            logger.info("Running periodic sweep")
            worker.sweep()
            last_sweep = now

        worker.run_once()


def main() -> None:
    settings = Settings()
    runtime = build_runtime(settings)
    stop_event = Event()

    def request_shutdown(signum: int, frame: Any) -> None:
        logger.info("Received signal %s; shutting down worker", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    try:
        _run_loop(runtime, settings, stop_event)
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
