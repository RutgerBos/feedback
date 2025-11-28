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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config.triad_loader import load_triad_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Loads configuration on startup and cleans up on shutdown.

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML syntax is invalid
        pydantic.ValidationError: If config structure is invalid

    Notes:
        - Fails fast: invalid config prevents application from starting
        - Config is stored in app.state for access by endpoints
    """
    # Startup: Load and validate configuration
    config_path = Path("config/triads.yaml")
    app.state.triad_config = load_triad_config(config_path)

    yield

    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="SenseMaker Feedback API",
    description="Narrative feedback collection and analysis system",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
