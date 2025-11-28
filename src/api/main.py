"""
FastAPI application entrypoint.

Responsibilities:
- Initialize FastAPI application
- Configure middleware and CORS
- Register routes
- Provide application metadata

Collaborators:
- FastAPI (framework)
- Health check endpoints

Notes:
- Simple bootstrap, no business logic
- Routes will be added as features are implemented
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="SenseMaker Feedback API",
    description="Narrative feedback collection and analysis system",
    version="0.1.0",
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
