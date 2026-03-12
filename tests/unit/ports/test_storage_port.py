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

    class IncompleteStorage(StoragePort):
        def get_story(self, story_id: str):
            pass

        def count_stories(self) -> int:
            return 0

        def list_stories(self, limit: int = 20, offset: int = 0) -> list:
            return []

    with pytest.raises(TypeError, match="abstract"):
        IncompleteStorage()


def test_storage_port_has_get_story_method():
    """StoragePort requires get_story implementation."""
    from src.ports.storage import StoragePort

    class IncompleteStorage(StoragePort):
        def save_story(self, story):
            pass

        def count_stories(self) -> int:
            return 0

        def list_stories(self, limit: int = 20, offset: int = 0) -> list:
            return []

    with pytest.raises(TypeError, match="abstract"):
        IncompleteStorage()


def test_storage_port_has_list_stories_method():
    """StoragePort requires list_stories implementation."""
    from src.ports.storage import StoragePort

    class IncompleteStorage(StoragePort):
        def save_story(self, story):
            pass

        def get_story(self, story_id: str):
            pass

        def count_stories(self) -> int:
            return 0

    with pytest.raises(TypeError, match="abstract"):
        IncompleteStorage()


def test_storage_port_has_count_stories_method():
    """StoragePort requires count_stories implementation."""
    from src.ports.storage import StoragePort

    class IncompleteStorage(StoragePort):
        def save_story(self, story):
            pass

        def get_story(self, story_id: str):
            pass

        def list_stories(self, limit: int = 20, offset: int = 0) -> list:
            return []

    with pytest.raises(TypeError, match="abstract"):
        IncompleteStorage()


def test_storage_port_has_update_story_entities_method():
    """StoragePort requires update_story_entities implementation."""
    from src.ports.storage import StoragePort

    class IncompleteStorage(StoragePort):
        def save_story(self, story):
            pass

        def get_story(self, story_id: str):
            pass

        def count_stories(self) -> int:
            return 0

        def list_stories(self, limit: int = 20, offset: int = 0) -> list:
            return []

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
            raise NotImplementedError()

        def count_stories(self) -> int:
            return 0

        def list_stories(self, limit: int = 20, offset: int = 0) -> list[Story]:
            return []

        def update_story_entities(self, story_id: str, entities: list, themes: list, processing_status: str) -> None:
            pass

    # Should be able to instantiate
    storage = FakeStorage()
    assert storage is not None
    assert isinstance(storage, StoragePort)
