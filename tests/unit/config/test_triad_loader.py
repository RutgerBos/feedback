"""Tests for triad configuration loader."""

import pytest
from pathlib import Path
import tempfile
import yaml


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
