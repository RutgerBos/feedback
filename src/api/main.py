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

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.dashboard import router as dashboard_router
from src.api.insights import router as insights_router
from src.api.patterns import router as patterns_router
from src.api.signifiers import router as signifiers_router
from src.api.stories import router as stories_router
from src.api.ui import router as ui_router
from src.composition import build_api_runtime
from src.config.settings import Settings
from src.config.triad_loader import load_triad_config


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

    runtime = build_api_runtime(_settings)
    runtime.install(app, _settings)

    try:
        yield
    finally:
        runtime.close()


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

# Static files and UI
_static_dir = str(Path(__file__).parent.parent.parent / "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")
app.include_router(ui_router)

# API routers
app.include_router(stories_router)
app.include_router(signifiers_router)
app.include_router(patterns_router)
app.include_router(insights_router)
app.include_router(dashboard_router)


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
