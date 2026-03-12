"""
Factory for creating LLM provider instances from configuration.
"""

import anthropic
from src.ports.llm import LLMPort


def create_llm_provider(config: dict) -> LLMPort:
    """
    Create an LLMPort implementation based on configuration.

    Args:
        config: Dict with at minimum a 'provider' key ('claude' or 'ollama').
                For 'claude': optionally 'api_key' (falls back to ANTHROPIC_API_KEY env var).
                For 'ollama': optionally 'base_url' and 'model'.

    Returns:
        LLMPort: Configured provider instance

    Raises:
        ValueError: If provider name is not recognised
    """
    provider = config.get("provider", "").lower()

    if provider == "claude":
        from src.adapters.claude_llm import ClaudeLLMAdapter
        api_key = config.get("api_key")
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        return ClaudeLLMAdapter(client=client)

    if provider == "ollama":
        from src.adapters.ollama_llm import OllamaLLMAdapter
        return OllamaLLMAdapter(
            base_url=config.get("base_url", OllamaLLMAdapter.DEFAULT_BASE_URL),
            model=config.get("model", OllamaLLMAdapter.DEFAULT_MODEL),
        )

    raise ValueError(f"Unknown LLM provider: '{provider}'. Expected 'claude' or 'ollama'.")
