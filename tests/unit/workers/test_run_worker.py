"""Worker process lifecycle tests."""

from unittest.mock import Mock

import pytest


def test_runtime_close_releases_all_clients_when_one_close_fails():
    from src.workers.run_worker import WorkerRuntime

    mongo = Mock()
    graph = Mock()
    redis = Mock()
    graph.close.side_effect = RuntimeError("graph close failed")
    runtime = WorkerRuntime(worker=Mock(), mongo_client=mongo, neo4j_driver=graph, redis_client=redis)

    runtime.close()

    mongo.close.assert_called_once_with()
    graph.close.assert_called_once_with()
    redis.close.assert_called_once_with()


def test_main_closes_runtime_when_worker_loop_exits(monkeypatch):
    import src.workers.run_worker as module

    runtime = Mock()
    monkeypatch.setattr(module, "build_runtime", lambda settings: runtime)
    monkeypatch.setattr(module.signal, "signal", Mock())
    monkeypatch.setattr(
        module,
        "_run_loop",
        Mock(side_effect=RuntimeError("loop stopped")),
    )

    with pytest.raises(RuntimeError, match="loop stopped"):
        module.main()

    runtime.close.assert_called_once_with()
