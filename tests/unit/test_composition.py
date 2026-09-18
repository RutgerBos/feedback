"""Tests for process composition and dependency providers."""

from types import SimpleNamespace
from unittest.mock import Mock


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
