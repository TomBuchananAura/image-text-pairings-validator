import os
import logging
from pathlib import Path
from typing import List, Optional

# Third-party imports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
# Assuming the router definition is correct:
from app.api.router import router as jobs_router


# ===============================================
# Logging Configuration
# ===============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S" 
)


def get_allowed_origins() -> List[str]:
    """
    Determines allowed CORS origins dynamically. 
    This function must be robust because the origin changes frequently (dev, stage, prod).
    Reads expected domains from environment variables for deployment flexibility.
    """
    # Local development URLs are mandatory for local testing.
    local_dev_urls = [
        "http://localhost:3000", 
        "http://127.0.0.1:5500",
    ]

    allowed: List[str] = list(set(local_dev_urls)) 

    # Read production origins from environment variables (Critical for Security)
    frontend_origin = os.environ.get("FRONTEND_DOMAIN")
    if frontend_origin:
        allowed.append(frontend_origin)
    
    return allowed


def create_app() -> FastAPI:
    """
    Initializes the FastAPI application gateway, configuring all necessary 
    middleware (CORS), static asset mounts, and API routes.
    This function is clean and agnostic to whether it's run locally or by Gunicorn.
    """
    app = FastAPI(
        title="Label Validation Pipeline API",
        description="Asynchronous image-text validation service.",
        version="1.0.0",
    )

    # --- Middleware: CORS Policy ---
    ALLOWED_ORIGINS = get_allowed_origins() 

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Static Files ---
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="root")

    # --- API Routing ---
    app.include_router(jobs_router, prefix="/api/v1", tags=["Jobs"])


    @app.get("/health")
    async def health_check():
        """Standard readiness check endpoint required by load balancers."""
        return {"status": "healthy"}

    return app


# Global application instance setup
# This object is what Gunicorn will import and run in production mode.
app = create_app()


# ===============================================
# LOCAL DEMO BOOTSTRAPPER 
# ===============================================
if __name__ == "__main__":
    import uvicorn
    """
    THIS BLOCK RUNS ONLY WHEN EXECUTED DIRECTLY (e.g., `python main.py`). 
    It provides the necessary startup logic for local reviewers/testing.

    When running on Render, this entire block is bypassed by Gunicorn.
    """
    # We use 'reload=True' only for development speed; remove it if troubleshooting memory leaks.
    logging.info("--- Running in DEVELOPMENT mode ---") 
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True
    )
