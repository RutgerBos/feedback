"""
Triad configuration loader.

Loads and validates triad definitions from YAML configuration files.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class TriadVertex(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent a validated vertex in a triad definition
    collaborators: []
    </crc>
    """

    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


class TriadDefinition(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent a valid three-vertex triad definition
      - Preserve unique vertex identities within the triad
    collaborators:
      - TriadVertex
    </crc>
    """

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    vertices: list[TriadVertex] = Field(..., min_length=3, max_length=3)

    @field_validator("vertices")
    @classmethod
    def validate_unique_vertex_ids(cls, v: list[TriadVertex]) -> list[TriadVertex]:
        """Ensure vertex IDs are unique within the triad."""
        vertex_ids = [vertex.id for vertex in v]
        if len(vertex_ids) != len(set(vertex_ids)):
            raise ValueError("Vertex IDs must be unique within a triad")
        return v


class TriadConfig(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent the application's validated triad catalogue
      - Preserve unique triad identities across the catalogue
    collaborators:
      - TriadDefinition
    </crc>
    """

    version: str = Field(..., min_length=1)
    context: str = Field(..., min_length=1)
    triads: list[TriadDefinition] = Field(..., min_length=1)

    @field_validator("triads")
    @classmethod
    def validate_unique_triad_ids(cls, v: list[TriadDefinition]) -> list[TriadDefinition]:
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
    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    return TriadConfig(**config_data)
