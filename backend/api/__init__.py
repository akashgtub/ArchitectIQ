"""ArchitectIQ API package exposing service facades and unified FastAPI routers."""

from backend.api.routes import router
from backend.api.service import optimize_architecture, run_simulation, simulate_failure

__all__ = [
    "optimize_architecture",
    "router",
    "run_simulation",
    "simulate_failure",
]
