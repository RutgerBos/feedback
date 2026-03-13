"""
FastAPI application entrypoint.

Responsibilities:
- Initialize FastAPI application
- Load and validate configuration on startup
- Configure middleware and CORS
- Register routes
- Provide application metadata

Collaborators:
- FastAPI (framework)
- Health check endpoints
- Config loader

Notes:
- Simple bootstrap, no business logic
- Routes will be added as features are implemented
- Config validation happens at startup (fail-fast)
"""

from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from src.config.settings import Settings
from src.config.triad_loader import load_triad_config
from src.api.stories import router as stories_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Loads configuration and creates infrastructure singletons on startup;
    tears them down cleanly on shutdown.

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML syntax is invalid
        pydantic.ValidationError: If config structure is invalid

    Notes:
        - Fails fast: invalid config prevents application from starting
        - Config and clients are stored in app.state for access by dependencies
        - MongoClient is a singleton: connection pool is shared across requests
    """
    # Load file-based config first — fails fast with no resources to clean up
    config_path = Path("config/triads.yaml")
    app.state.triad_config = load_triad_config(config_path)

    # Create infrastructure singletons only after config is validated
    settings = Settings()
    app.state.settings = settings
    app.state.mongo_client = MongoClient(settings.mongodb_url)

    yield

    # Shutdown: close the connection pool
    app.state.mongo_client.close()


_settings = Settings()

app = FastAPI(
    title="SenseMaker Feedback API",
    description="Narrative feedback collection and analysis system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(stories_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Dictionary with status and version information
    """
    return {
        "status": "healthy",
        "version": "0.1.0",
    }


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint with API information.

    Returns:
        Dictionary with welcome message and documentation link
    """
    return {
        "message": "SenseMaker Feedback API",
        "docs": "/docs",
    }
