"""Tests for LLM provider factory."""

import pytest
from unittest.mock import patch, MagicMock


def test_factory_creates_claude_adapter_for_claude_config():
    """Factory returns ClaudeLLMAdapter when config provider is 'claude'."""
    from src.adapters.llm_factory import create_llm_provider
    from src.adapters.claude_llm import ClaudeLLMAdapter

    fake_client = MagicMock()
    with patch("src.adapters.llm_factory.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = fake_client
        provider = create_llm_provider({"provider": "claude", "api_key": "test-key"})

    assert isinstance(provider, ClaudeLLMAdapter)
    mock_anthropic.Anthropic.assert_called_once_with(api_key="test-key")


def test_factory_passes_api_key_to_claude_client():
    """Factory passes api_key from config to the Anthropic client."""
    with patch("src.adapters.llm_factory.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = MagicMock()
        from src.adapters.llm_factory import create_llm_provider
        create_llm_provider({"provider": "claude", "api_key": "my-secret"})

    mock_anthropic.Anthropic.assert_called_with(api_key="my-secret")


def test_factory_creates_ollama_adapter_for_ollama_config():
    """Factory returns OllamaLLMAdapter when config provider is 'ollama'."""
    from src.adapters.llm_factory import create_llm_provider
    from src.adapters.ollama_llm import OllamaLLMAdapter

    provider = create_llm_provider({"provider": "ollama"})

    assert isinstance(provider, OllamaLLMAdapter)


def test_factory_uses_custom_ollama_base_url():
    """Factory passes base_url through to OllamaLLMAdapter."""
    from src.adapters.llm_factory import create_llm_provider
    from src.adapters.ollama_llm import OllamaLLMAdapter

    provider = create_llm_provider({"provider": "ollama", "base_url": "http://myserver:11434"})

    assert isinstance(provider, OllamaLLMAdapter)
    assert provider.base_url == "http://myserver:11434"


def test_factory_uses_custom_ollama_model():
    """Factory passes model through to OllamaLLMAdapter."""
    from src.adapters.llm_factory import create_llm_provider
    from src.adapters.ollama_llm import OllamaLLMAdapter

    provider = create_llm_provider({"provider": "ollama", "model": "mistral"})

    assert isinstance(provider, OllamaLLMAdapter)
    assert provider.model == "mistral"


def test_factory_raises_for_unknown_provider():
    """Factory raises ValueError for unrecognised provider name."""
    from src.adapters.llm_factory import create_llm_provider

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_provider({"provider": "gpt-99"})
