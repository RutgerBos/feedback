"""Tests for OllamaLLMAdapter."""

import json
from src.ports.llm import LLMPort, EntityExtraction


def make_fake_http_client(response_text: str):
    """Create a fake HTTP client that returns a canned JSON response."""

    class FakeResponse:
        def json(self):
            return {"response": response_text}

    class FakeClient:
        def post(self, url, **kwargs):
            return FakeResponse()

    return FakeClient()


def test_ollama_adapter_implements_llm_port():
    """OllamaLLMAdapter is a valid LLMPort implementation."""
    from src.adapters.ollama_llm import OllamaLLMAdapter

    client = make_fake_http_client('{"entities": [], "themes": []}')
    adapter = OllamaLLMAdapter(http_client=client)

    assert isinstance(adapter, LLMPort)


def test_ollama_adapter_extract_entities_returns_entity_extraction():
    """extract_entities parses ollama JSON response into EntityExtraction."""
    from src.adapters.ollama_llm import OllamaLLMAdapter

    response = json.dumps({
        "entities": [{"name": "CI pipeline", "type": "tool"}],
        "themes": [{"name": "tooling issues", "description": "Problems with dev tools"}],
    })
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.extract_entities("I had to restart the CI pipeline.")

    assert isinstance(result, EntityExtraction)
    assert result.entities[0]["name"] == "CI pipeline"
    assert len(result.themes) == 1


def test_ollama_adapter_extract_themes_returns_list_of_strings():
    """extract_themes parses ollama JSON response into list of strings."""
    from src.adapters.ollama_llm import OllamaLLMAdapter

    response = json.dumps({"themes": ["tooling reliability", "developer friction"]})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.extract_themes("CI keeps failing on us.")

    assert result == ["tooling reliability", "developer friction"]


def test_ollama_adapter_extract_relationships_returns_list_of_dicts():
    """extract_relationships parses ollama JSON response into list of dicts."""
    from src.adapters.ollama_llm import OllamaLLMAdapter

    response = json.dumps({
        "relationships": [{"source": "CI", "target": "deploy", "relationship": "BLOCKS"}]
    })
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.extract_relationships("CI failures blocked deploys.")

    assert result[0]["source"] == "CI"
    assert result[0]["relationship"] == "BLOCKS"
