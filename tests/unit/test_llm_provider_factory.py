"""Tests for LLM provider factory."""

import pytest


def test_factory_creates_claude_adapter_for_claude_config():
    """Factory returns ClaudeLLMAdapter when config provider is 'claude'."""
    from src.adapters.llm_factory import create_llm_provider
    from src.adapters.claude_llm import ClaudeLLMAdapter

    provider = create_llm_provider({"provider": "claude", "api_key": "test-key"})

    assert isinstance(provider, ClaudeLLMAdapter)


def test_factory_creates_ollama_adapter_for_ollama_config():
    """Factory returns OllamaLLMAdapter when config provider is 'ollama'."""
    from src.adapters.llm_factory import create_llm_provider
    from src.adapters.ollama_llm import OllamaLLMAdapter

    provider = create_llm_provider({"provider": "ollama", "base_url": "http://localhost:11434"})

    assert isinstance(provider, OllamaLLMAdapter)


def test_factory_uses_custom_ollama_base_url():
    """Factory passes base_url through to OllamaLLMAdapter."""
    from src.adapters.llm_factory import create_llm_provider
    from src.adapters.ollama_llm import OllamaLLMAdapter

    provider = create_llm_provider({"provider": "ollama", "base_url": "http://myserver:11434"})

    assert isinstance(provider, OllamaLLMAdapter)
    assert provider.base_url == "http://myserver:11434"


def test_factory_raises_for_unknown_provider():
    """Factory raises ValueError for unrecognised provider name."""
    from src.adapters.llm_factory import create_llm_provider

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_provider({"provider": "gpt-99"})
