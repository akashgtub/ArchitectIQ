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
    title="ArchitectIQ — Autonomous System Architecture Analysis & Simulation Agent",
    description=(
        "Unified autonomous AI agent for architecture diagram understanding, "
        "graph validation, discrete-event simulation, deterministic optimization, "
        "and chaos resilience testing."
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

# Mount frontend files and assets
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import HTTPException as FastAPIHTTPException

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
dist_index = frontend_dist / "index.html"
dist_assets = frontend_dist / "assets"

if dist_assets.is_dir():
    app.mount("/assets", StaticFiles(directory=str(dist_assets)), name="frontend_assets")


def _get_frontend_response():
    if dist_index.is_file():
        return FileResponse(str(dist_index))
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error_code": "ERR_FRONTEND_NOT_BUILT",
            "message": (
                "Frontend production build artifacts were not found in 'frontend/dist'. "
                "Ensure 'npm run build' was executed during the deployment build process."
            ),
        },
    )


@app.get("/", tags=["Frontend"])
async def serve_frontend_root():
    return _get_frontend_response()


@app.get("/{full_path:path}", tags=["Frontend"], include_in_schema=False)
async def serve_frontend_fallback(full_path: str):
    # Guard API, health, docs, and schema endpoints against falling back to frontend
    if (
        full_path.startswith("api/")
        or full_path == "api"
        or full_path.startswith("health")
        or full_path.startswith("docs")
        or full_path.startswith("redoc")
        or full_path == "openapi.json"
    ):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error_code": "ERR_NOT_FOUND", "message": f"Resource '/{full_path}' not found."},
        )

    # Check for root static assets inside dist (e.g., favicon, icons, etc.)
    static_file = frontend_dist / full_path
    if static_file.is_file():
        return FileResponse(str(static_file))

    # Also check dist/assets in case asset is requested without /assets prefix
    asset_file = dist_assets / full_path
    if asset_file.is_file():
        return FileResponse(str(asset_file))

    # SPA routing fallback
    return _get_frontend_response()



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, (FastAPIHTTPException, StarletteHTTPException)):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail if isinstance(exc.detail, (dict, list)) else {"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    logger.error("Unhandled exception at %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "ERR_INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred during processing. Please review request or logs.",
        },
    )


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)

