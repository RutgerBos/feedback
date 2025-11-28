"""Tests for StoragePort interface."""

import pytest
from abc import ABC


def test_storage_port_is_abstract():
    """StoragePort cannot be instantiated directly."""
    from src.ports.storage import StoragePort

    with pytest.raises(TypeError, match="abstract"):
        StoragePort()


def test_storage_port_has_save_story_method():
    """StoragePort requires save_story implementation."""
    from src.ports.storage import StoragePort
    from src.domain.models import Story, TriadPlacement, TriadCoordinates

    # Create a concrete implementation missing save_story
    class IncompleteStorage(StoragePort):
        def get_story(self, story_id: str):
            pass

    # Should not be able to instantiate
    with pytest.raises(TypeError, match="abstract"):
        IncompleteStorage()


def test_storage_port_has_get_story_method():
    """StoragePort requires get_story implementation."""
    from src.ports.storage import StoragePort

    # Create a concrete implementation missing get_story
    class IncompleteStorage(StoragePort):
        def save_story(self, story):
            pass

    # Should not be able to instantiate
    with pytest.raises(TypeError, match="abstract"):
        IncompleteStorage()


def test_can_implement_storage_port():
    """Can create a valid StoragePort implementation."""
    from src.ports.storage import StoragePort
    from src.domain.models import Story

    class FakeStorage(StoragePort):
        def save_story(self, story: Story) -> str:
            return "fake-id-123"

        def get_story(self, story_id: str) -> Story:
            # Just a stub for testing
            raise NotImplementedError()

    # Should be able to instantiate
    storage = FakeStorage()
    assert storage is not None
    assert isinstance(storage, StoragePort)
