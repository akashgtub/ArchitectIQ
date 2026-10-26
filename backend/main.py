"""
ArchPilot AI - Backend Main Application
Member 1: Architecture Understanding & Root-Cause Investigation

Entrypoint for FastAPI application.
Configures CORS, routers, logging, and error handling.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router as api_v1_router
from backend.config import settings
from backend.shared.schemas import SCHEMA_VERSION

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("archpilot.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ArchPilot AI (Member 1 Engine)...")
    logger.info("Model Configured: %s", settings.gemini_model_id)
    logger.info("Simulator Base URL: %s (Mock Mode: %s)", settings.simulator_base_url or "None", settings.use_mock_simulator)
    logger.info("Shared Schema Version: %s", SCHEMA_VERSION)
    yield
    logger.info("Shutting down ArchPilot AI (Member 1 Engine)...")


app = FastAPI(
    title="ArchPilot AI - The Self-Testing System Design Agent",
    description=(
        "Member 1: Architecture Understanding & Root-Cause Investigation. "
        "Interprets architecture diagrams, validates system topology, "
        "orchestrates baseline simulations, diagnoses bottlenecks, and produces "
        "evidence-based handoffs for Member 2 optimization."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend / external integration
allow_wildcard = "*" in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=not allow_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_v1_router)

# Mount frontend files if available
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
frontend_src = Path(__file__).resolve().parent.parent / "frontend"

if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="frontend_assets")
    @app.get("/", tags=["Frontend"])
    async def serve_frontend():
        return FileResponse(str(frontend_dist / "index.html"))
elif frontend_src.is_dir() and (frontend_src / "index.html").is_file():
    app.mount("/src", StaticFiles(directory=str(frontend_src / "src")), name="frontend_src")
    @app.get("/", tags=["Frontend"])
    async def serve_frontend():
        return FileResponse(str(frontend_src / "index.html"))

@app.get("/health", tags=["System"])
async def root_health():
    return {
        "status": "healthy",
        "service": "ArchitectIQ",
        "schema_version": SCHEMA_VERSION,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception at %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "ERR_INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred during processing. Please review request or logs.",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
