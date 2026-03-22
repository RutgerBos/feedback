"""
Domain exceptions for the ports layer.

These exceptions are raised by StoragePort implementations and caught
by the application layer. Keeping them here ensures the API layer
never needs to import from concrete adapters.
"""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist in storage."""
    pass


class StorageError(Exception):
    """Raised when a storage operation fails due to infrastructure issues."""
    pass


class LLMError(Exception):
    """Raised when an LLM API call fails or its response cannot be parsed."""
    pass


class GraphError(Exception):
    """Raised when a graph database operation fails."""
    pass


class QueryTranslationError(Exception):
    """Raised when the LLM cannot translate a natural language question into a graph query."""
    pass
