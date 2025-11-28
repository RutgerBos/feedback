"""Test that ports have no infrastructure dependencies."""

import ast
import importlib.util
from pathlib import Path


def test_ports_have_no_infrastructure_imports():
    """
    Ports should not import from infrastructure libraries.

    This ensures the domain layer stays independent of infrastructure choices.
    """
    # List of forbidden infrastructure imports
    forbidden_imports = [
        "pymongo",
        "neo4j",
        "redis",
        "anthropic",
        "openai",
        "psycopg2",
        "sqlalchemy",
        "motor",  # async MongoDB
    ]

    ports_dir = Path("src/ports")
    port_files = list(ports_dir.glob("*.py"))

    # Exclude __init__.py
    port_files = [f for f in port_files if f.name != "__init__.py"]

    for port_file in port_files:
        with open(port_file, "r") as f:
            tree = ast.parse(f.read(), filename=str(port_file))

        # Collect all imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split(".")[0])

        # Check for forbidden imports
        forbidden_found = [imp for imp in imports if imp in forbidden_imports]

        assert (
            not forbidden_found
        ), f"{port_file.name} imports forbidden infrastructure: {forbidden_found}"


def test_ports_only_import_from_domain():
    """
    Ports should only import from domain and standard library.

    Valid imports: domain models, ABC, typing, etc.
    """
    ports_dir = Path("src/ports")
    port_files = list(ports_dir.glob("*.py"))
    port_files = [f for f in port_files if f.name != "__init__.py"]

    allowed_prefixes = [
        "src.domain",  # Domain models
        "abc",  # Abstract base classes
        "typing",  # Type hints
        "dataclasses",  # Data structures
        "datetime",  # Date/time
        "enum",  # Enumerations
    ]

    for port_file in port_files:
        with open(port_file, "r") as f:
            tree = ast.parse(f.read(), filename=str(port_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and not any(
                    node.module.startswith(prefix) for prefix in allowed_prefixes
                ):
                    # Allow relative imports within src
                    if not node.module.startswith("src"):
                        assert False, (
                            f"{port_file.name} imports from unexpected module: "
                            f"{node.module}. Ports should only import from domain or stdlib."
                        )
