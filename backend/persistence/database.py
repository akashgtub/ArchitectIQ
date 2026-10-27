"""
ArchitectIQ - SQLite Database Engine
Provides persistence for architecture models and simulation execution history.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse

from backend.config import settings

logger = logging.getLogger("architectiq.persistence.database")


def get_sqlite_db_path() -> Path:
    """Extract filesystem path from DATABASE_URL."""
    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        rel_or_abs = db_url.replace("sqlite:///", "")
        path = Path(rel_or_abs)
        if not path.is_absolute():
            # Resolve relative to repo root
            root_dir = Path(__file__).resolve().parent.parent.parent
            path = (root_dir / path).resolve()
        return path
    # Default fallback
    return Path(__file__).resolve().parent.parent.parent / "architectiq.db"


def init_db() -> None:
    """Initialize SQLite database tables and indexes."""
    db_path = get_sqlite_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        # Architectures table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS architectures (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                schema_version TEXT DEFAULT '1.0',
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        # Simulation run history table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS simulations (
                id TEXT PRIMARY KEY,
                architecture_id TEXT NOT NULL,
                run_type TEXT NOT NULL,
                workload TEXT DEFAULT '{}',
                result TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        # Indexes for fast lookup
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_simulations_arch_id ON simulations(architecture_id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_simulations_created_at ON simulations(created_at DESC);"
        )
        conn.commit()
    logger.info("Database initialized successfully at %s", db_path)


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Yields a configured SQLite connection context with row factories."""
    db_path = get_sqlite_db_path()
    if not db_path.exists():
        init_db()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
