"""Tests for triad configuration loader."""

import pytest
from pathlib import Path
import tempfile
import yaml
from pydantic import ValidationError


def test_load_valid_triad_config():
    """Can load a valid triad configuration from YAML file."""
    # Arrange: Create a minimal valid config
    config_data = {
        "version": "1.0",
        "context": "test",
        "triads": [
            {
                "id": "test_triad",
                "name": "Test Triad",
                "description": "A test triad",
                "vertices": [
                    {
                        "id": "vertex_a",
                        "label": "Vertex A",
                        "description": "First vertex",
                    },
                    {
                        "id": "vertex_b",
                        "label": "Vertex B",
                        "description": "Second vertex",
                    },
                    {
                        "id": "vertex_c",
                        "label": "Vertex C",
                        "description": "Third vertex",
                    },
                ],
            }
        ],
    }

    # Write to a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = Path(f.name)

    try:
        # Act: Load the config
        from src.config.triad_loader import load_triad_config

        config = load_triad_config(config_path)

        # Assert: Config is loaded correctly
        assert config.version == "1.0"
        assert config.context == "test"
        assert len(config.triads) == 1
        assert config.triads[0].id == "test_triad"
        assert config.triads[0].name == "Test Triad"
        assert len(config.triads[0].vertices) == 3
        assert config.triads[0].vertices[0].id == "vertex_a"
    finally:
        # Cleanup
        config_path.unlink()


def test_rejects_triad_with_wrong_vertex_count():
    """Validates that each triad has exactly 3 vertices."""
    from src.config.triad_loader import load_triad_config

    # Arrange: Config with only 2 vertices
    config_data = {
        "version": "1.0",
        "context": "test",
        "triads": [
            {
                "id": "test_triad",
                "name": "Test Triad",
                "description": "A test triad",
                "vertices": [
                    {"id": "vertex_a", "label": "Vertex A", "description": "First"},
                    {"id": "vertex_b", "label": "Vertex B", "description": "Second"},
                ],
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = Path(f.name)

    try:
        # Act & Assert: Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            load_triad_config(config_path)

        # Check error mentions vertices
        assert "vertices" in str(exc_info.value).lower()
    finally:
        config_path.unlink()


def test_rejects_duplicate_vertex_ids():
    """Rejects config with duplicate vertex IDs within a triad."""
    from src.config.triad_loader import load_triad_config

    # Arrange: Config with duplicate vertex IDs
    config_data = {
        "version": "1.0",
        "context": "test",
        "triads": [
            {
                "id": "test_triad",
                "name": "Test Triad",
                "description": "A test triad",
                "vertices": [
                    {"id": "vertex_a", "label": "Vertex A", "description": "First"},
                    {"id": "vertex_a", "label": "Duplicate", "description": "Duplicate ID"},
                    {"id": "vertex_c", "label": "Vertex C", "description": "Third"},
                ],
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = Path(f.name)

    try:
        # Act & Assert: Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            load_triad_config(config_path)

        # Check error mentions uniqueness
        assert "unique" in str(exc_info.value).lower()
    finally:
        config_path.unlink()


def test_rejects_duplicate_triad_ids():
    """Rejects config with duplicate triad IDs."""
    from src.config.triad_loader import load_triad_config

    # Arrange: Config with duplicate triad IDs
    config_data = {
        "version": "1.0",
        "context": "test",
        "triads": [
            {
                "id": "duplicate_triad",
                "name": "First Triad",
                "description": "First",
                "vertices": [
                    {"id": "a1", "label": "A", "description": "First"},
                    {"id": "b1", "label": "B", "description": "Second"},
                    {"id": "c1", "label": "C", "description": "Third"},
                ],
            },
            {
                "id": "duplicate_triad",
                "name": "Second Triad",
                "description": "Duplicate ID",
                "vertices": [
                    {"id": "a2", "label": "A", "description": "First"},
                    {"id": "b2", "label": "B", "description": "Second"},
                    {"id": "c2", "label": "C", "description": "Third"},
                ],
            },
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = Path(f.name)

    try:
        # Act & Assert: Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            load_triad_config(config_path)

        # Check error mentions uniqueness
        assert "unique" in str(exc_info.value).lower()
    finally:
        config_path.unlink()


def test_rejects_missing_required_fields():
    """Rejects config with missing required fields."""
    from src.config.triad_loader import load_triad_config

    # Arrange: Config missing 'name' field in triad
    config_data = {
        "version": "1.0",
        "context": "test",
        "triads": [
            {
                "id": "test_triad",
                # missing "name"
                "description": "A test triad",
                "vertices": [
                    {"id": "a", "label": "A", "description": "First"},
                    {"id": "b", "label": "B", "description": "Second"},
                    {"id": "c", "label": "C", "description": "Third"},
                ],
            }
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = Path(f.name)

    try:
        # Act & Assert: Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            load_triad_config(config_path)

        # Check error mentions the missing field
        assert "name" in str(exc_info.value).lower()
    finally:
        config_path.unlink()
