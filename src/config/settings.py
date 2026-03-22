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
    - CORS_ORIGINS must be a JSON array: '["http://a.com","http://b.com"]'
    """

    mongodb_url: str = "mongodb://admin:password@mongodb:27017/"
    mongodb_database: str = "feedback"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    neo4j_url: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    proximity_threshold: float = 0.3
    llm_provider: str = "none"
    llm_model: str = "llama3"
    local_model_url: str = "http://localhost:11434"
    redis_url: str = "redis://localhost:6379/0"
    worker_queue_key: str = "feedback:story-processing:v1"
    worker_sweep_interval: int = 60  # seconds between periodic sweeps
    worker_dequeue_timeout: int = 5  # seconds to block on brpop

    model_config = {"env_file": ".env", "extra": "ignore"}
