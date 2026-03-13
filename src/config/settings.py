"""
Application settings loaded from environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Responsibilities:
    - Load infrastructure connection settings from environment
    - Provide typed, validated configuration to the application

    Collaborators:
    - None (value object, read at startup)

    Notes:
    - Values come from environment variables or .env file
    - All fields have sensible defaults for local development
    """

    mongodb_url: str = "mongodb://admin:password@mongodb:27017/"
    mongodb_database: str = "feedback"

    model_config = {"env_file": ".env", "extra": "ignore"}
