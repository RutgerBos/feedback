"""
Triad configuration loader.

Loads and validates triad definitions from YAML configuration files.
"""

from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, Field, field_validator


class TriadVertex(BaseModel):
    """
    Responsibilities:
    - Hold single vertex data (id, label, description)
    - Ensure vertex is always valid when constructed

    Collaborators:
    - None (value object)

    Notes:
    - Immutable after creation
    - Validation in constructor
    """

    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


class TriadDefinition(BaseModel):
    """
    Responsibilities:
    - Hold complete triad definition (id, name, description, vertices)
    - Ensure triad has exactly 3 vertices
    - Ensure vertex IDs are unique within triad

    Collaborators:
    - TriadVertex (value object)

    Notes:
    - Immutable after creation
    - Validates structure in constructor
    """

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    vertices: List[TriadVertex] = Field(..., min_length=3, max_length=3)

    @field_validator("vertices")
    @classmethod
    def validate_unique_vertex_ids(cls, v: List[TriadVertex]) -> List[TriadVertex]:
        """Ensure vertex IDs are unique within the triad."""
        vertex_ids = [vertex.id for vertex in v]
        if len(vertex_ids) != len(set(vertex_ids)):
            raise ValueError("Vertex IDs must be unique within a triad")
        return v


class TriadConfig(BaseModel):
    """
    Responsibilities:
    - Hold top-level config structure (version, context, triads)
    - Ensure triad IDs are unique across config
    - Provide validated config data to application

    Collaborators:
    - TriadDefinition (value object)

    Notes:
    - Immutable after creation
    - Validates entire config structure
    """

    version: str = Field(..., min_length=1)
    context: str = Field(..., min_length=1)
    triads: List[TriadDefinition] = Field(..., min_length=1)

    @field_validator("triads")
    @classmethod
    def validate_unique_triad_ids(cls, v: List[TriadDefinition]) -> List[TriadDefinition]:
        """Ensure triad IDs are unique across the config."""
        triad_ids = [triad.id for triad in v]
        if len(triad_ids) != len(set(triad_ids)):
            raise ValueError("Triad IDs must be unique")
        return v


def load_triad_config(config_path: Path) -> TriadConfig:
    """
    Load and validate triad configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Validated TriadConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML syntax is invalid
        pydantic.ValidationError: If config structure is invalid
    """
    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)

    return TriadConfig(**config_data)
