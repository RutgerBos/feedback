"""Tests for process composition and dependency providers."""

from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.params import Depends


def test_configured_llm_uses_settings_for_provider_selection(monkeypatch):
    from src import composition

    provider = Mock()
    factory = Mock(return_value=provider)
    monkeypatch.setattr(composition, "create_llm_provider", factory)
    settings = SimpleNamespace(
        llm_provider="ollama",
        llm_model="mistral",
        local_model_url="http://model:11434",
    )

    result = composition.create_configured_llm(settings)

    assert result is provider
    factory.assert_called_once_with(
        {
            "provider": "ollama",
            "model": "mistral",
            "base_url": "http://model:11434",
        }
    )


def test_get_llm_returns_process_scoped_provider():
    from src.composition import get_llm

    provider = Mock()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(llm=provider)))

    assert get_llm(request) is provider
    assert get_llm(request) is provider


def test_worker_entrypoint_uses_shared_runtime_builder():
    from src.composition import build_worker_runtime
    from src.workers.run_worker import build_runtime

    assert build_runtime is build_worker_runtime


def test_api_runtime_close_releases_all_clients_when_one_close_fails():
    from src.composition import ApiRuntime

    mongo = Mock()
    graph = Mock()
    redis = Mock()
    graph.close.side_effect = RuntimeError("graph close failed")
    runtime = ApiRuntime(
        llm=Mock(),
        mongo_client=mongo,
        neo4j_driver=graph,
        redis_client=redis,
        worker_queue=Mock(),
    )

    runtime.close()

    mongo.close.assert_called_once_with()
    graph.close.assert_called_once_with()
    redis.close.assert_called_once_with()


def test_build_api_runtime_constructs_process_resources(monkeypatch):
    from src import composition

    settings = SimpleNamespace(
        llm_provider="none",
        llm_model="unused",
        local_model_url="http://model",
        mongodb_url="mongodb://db",
        neo4j_url="bolt://graph",
        neo4j_user="neo4j-user",
        neo4j_password="neo4j-password",
        redis_url="redis://queue",
        worker_queue_key="stories",
        worker_visibility_timeout=90,
    )
    llm = Mock()
    mongo = Mock()
    graph = Mock()
    redis = Mock()
    queue = Mock()
    monkeypatch.setattr(composition, "create_configured_llm", Mock(return_value=llm))
    mongo_factory = Mock(return_value=mongo)
    graph_factory = Mock(return_value=graph)
    redis_factory = Mock(return_value=redis)
    queue_factory = Mock(return_value=queue)
    monkeypatch.setattr(composition, "MongoClient", mongo_factory)
    monkeypatch.setattr(composition.neo4j.GraphDatabase, "driver", graph_factory)
    monkeypatch.setattr(composition.redis_lib, "from_url", redis_factory)
    monkeypatch.setattr(composition, "WorkerQueue", queue_factory)

    runtime = composition.build_api_runtime(settings)

    assert runtime.llm is llm
    assert runtime.mongo_client is mongo
    assert runtime.neo4j_driver is graph
    assert runtime.redis_client is redis
    assert runtime.worker_queue is queue
    mongo_factory.assert_called_once_with("mongodb://db")
    graph_factory.assert_called_once_with(
        "bolt://graph",
        auth=("neo4j-user", "neo4j-password"),
    )
    redis_factory.assert_called_once_with("redis://queue")
    queue_factory.assert_called_once_with(
        redis=redis,
        queue_key="stories",
        visibility_timeout=90,
    )


def test_ui_dashboard_uses_shared_composition_provider():
    import inspect

    from src.api.ui import dashboard_data
    from src.composition import get_dashboard_service

    dependency = inspect.signature(dashboard_data).parameters["service"].default

    assert isinstance(dependency, Depends)
    assert dependency.dependency is get_dashboard_service
