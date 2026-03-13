"""Tests for OllamaLLMAdapter."""

import json
import pytest
from src.ports.llm import LLMPort, EntityExtraction


def make_fake_http_client(response_text: str):
    """Create a fake HTTP client that returns a canned JSON response."""

    class FakeResponse:
        def raise_for_status(self):
            pass  # success — no-op

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


def test_ollama_adapter_raises_on_http_error():
    """extract_entities raises LLMError when the HTTP response indicates an error."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    class ErrorResponse:
        def raise_for_status(self):
            raise Exception("500 Server Error")
        def json(self):
            return {"error": "model not found"}

    class ErrorClient:
        def post(self, url, **kwargs):
            return ErrorResponse()

    adapter = OllamaLLMAdapter(http_client=ErrorClient())

    with pytest.raises(LLMError):
        adapter.extract_entities("some story text here")


def test_ollama_adapter_extract_entities_raises_on_missing_key():
    """extract_entities raises LLMError when expected keys are absent."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    adapter = OllamaLLMAdapter(http_client=make_fake_http_client("{}"))

    with pytest.raises(LLMError):
        adapter.extract_entities("some story text here")


def test_ollama_adapter_extract_entities_raises_on_bad_shape():
    """extract_entities raises LLMError when response has wrong shape."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    bad_response = json.dumps({"entities": "not-a-list", "themes": []})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(bad_response))

    with pytest.raises(LLMError):
        adapter.extract_entities("some story text here")


def test_ollama_adapter_extract_themes_raises_on_bad_shape():
    """extract_themes raises LLMError when themes is not a list."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    bad_response = json.dumps({"themes": "not-a-list"})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(bad_response))

    with pytest.raises(LLMError):
        adapter.extract_themes("some story text here")


def test_ollama_adapter_extract_themes_raises_on_non_string_elements():
    """extract_themes raises LLMError when any element is not a string.

    Story.themes is List[str]; non-string elements would cause a Pydantic
    ValidationError on readback. The adapter must catch this at the boundary.
    """
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    bad_response = json.dumps({"themes": ["valid theme", 42, {"name": "oops"}]})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(bad_response))

    with pytest.raises(LLMError):
        adapter.extract_themes("some story text here")


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
