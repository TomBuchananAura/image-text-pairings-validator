import os
import logging
from pathlib import Path

# Third-party imports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Internal router imports
from app.api.router import router as jobs_router


# Configure general application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S"
)


def create_app() -> FastAPI:
    """
    Initializes and configures the FastAPI application instance.
    Sets up middleware, static files, and API routes.
    """
    app = FastAPI(
        title="Label Validation Pipeline API",
        description="Asynchronous image-text validation pipeline.",
        version="1.0.0",
    )

    # Define allowed origins for CORS policy
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "https://yourusername.github.io",
    ]

    # Configure Cross-Origin Resource Sharing (CORS) middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files directory
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)))
        # Ensure root path serves static files if no specific endpoint is hit
        app.mount("/", StaticFiles(directory=str(static_dir)))

    # Include the core API router with a base prefix
    app.include_router(jobs_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        """Provides a basic status check endpoint."""
        return {"status": "healthy"}

    return app


# Global application instance setup
app = create_app()


if __name__ == "__main__":
    import uvicorn
    # Use reload=True only for development; consider removing it in final production deployment.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
