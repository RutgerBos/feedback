"""Tests for ClaudeLLMAdapter."""

import json
import pytest
from src.ports.llm import LLMPort, EntityExtraction


def make_fake_anthropic_client(response_text: str):
    """Create a fake Anthropic client that returns canned JSON responses."""

    class FakeMessage:
        class FakeContent:
            text = response_text

        content = [FakeContent()]

    class FakeMessages:
        def create(self, **kwargs):
            return FakeMessage()

    class FakeClient:
        messages = FakeMessages()

    return FakeClient()


def test_claude_adapter_implements_llm_port():
    """ClaudeLLMAdapter is a valid LLMPort implementation."""
    from src.adapters.claude_llm import ClaudeLLMAdapter

    client = make_fake_anthropic_client('{"entities": [], "themes": []}')
    adapter = ClaudeLLMAdapter(client=client)

    assert isinstance(adapter, LLMPort)


def test_claude_adapter_extract_entities_returns_entity_extraction():
    """extract_entities parses Anthropic JSON response into EntityExtraction."""
    from src.adapters.claude_llm import ClaudeLLMAdapter

    response = json.dumps({
        "entities": [
            {"name": "CI pipeline", "type": "tool"},
            {"name": "deployment", "type": "process"},
        ],
        "themes": [{"name": "automation friction", "description": "Manual steps causing delays"}],
    })
    adapter = ClaudeLLMAdapter(client=make_fake_anthropic_client(response))

    result = adapter.extract_entities("I had to restart the CI pipeline three times today.")

    assert isinstance(result, EntityExtraction)
    assert len(result.entities) == 2
    assert result.entities[0]["name"] == "CI pipeline"
    assert len(result.themes) == 1


def test_claude_adapter_extract_themes_returns_list_of_strings():
    """extract_themes parses Anthropic JSON response into list of strings."""
    from src.adapters.claude_llm import ClaudeLLMAdapter

    response = json.dumps({
        "themes": ["automation friction", "tooling reliability", "developer experience"]
    })
    adapter = ClaudeLLMAdapter(client=make_fake_anthropic_client(response))

    result = adapter.extract_themes("I had to restart the CI pipeline three times today.")

    assert isinstance(result, list)
    assert result == ["automation friction", "tooling reliability", "developer experience"]


def test_claude_adapter_extract_relationships_returns_list_of_dicts():
    """extract_relationships parses Anthropic JSON response into list of dicts."""
    from src.adapters.claude_llm import ClaudeLLMAdapter

    response = json.dumps({
        "relationships": [
            {"source": "CI pipeline", "target": "deployment", "relationship": "BLOCKS"},
        ]
    })
    adapter = ClaudeLLMAdapter(client=make_fake_anthropic_client(response))

    result = adapter.extract_relationships("CI failures blocked our deployment.")

    assert isinstance(result, list)
    assert result[0]["source"] == "CI pipeline"
    assert result[0]["relationship"] == "BLOCKS"
