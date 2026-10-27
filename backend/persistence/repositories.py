"""
ArchitectIQ - Repositories for Architecture and Simulation Persistence
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.persistence.database import get_db_connection


class ArchitectureRepository:
    """Manages persistence of system architecture specifications."""

    @staticmethod
    def save_architecture(
        arch_id: str,
        name: str,
        data: Dict[str, Any],
        description: str = "",
        schema_version: str = "1.0",
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        json_data = json.dumps(data)

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO architectures (id, name, description, schema_version, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    data=excluded.data,
                    updated_at=excluded.updated_at;
                """,
                (arch_id, name, description, schema_version, json_data, now, now),
            )

        return {
            "id": arch_id,
            "name": name,
            "description": description,
            "schema_version": schema_version,
            "created_at": now,
            "updated_at": now,
            "data": data,
        }

    @staticmethod
    def get_architecture(arch_id: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, description, schema_version, data, created_at, updated_at FROM architectures WHERE id = ?;",
                (arch_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "schema_version": row["schema_version"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "data": json.loads(row["data"]),
            }

    @staticmethod
    def list_architectures(limit: int = 50) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, description, schema_version, created_at, updated_at FROM architectures ORDER BY updated_at DESC LIMIT ?;",
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "schema_version": row["schema_version"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    @staticmethod
    def delete_architecture(arch_id: str) -> bool:
        with get_db_connection() as conn:
            cursor = conn.execute("DELETE FROM architectures WHERE id = ?;", (arch_id,))
            return cursor.rowcount > 0


class SimulationRepository:
    """Manages persistence of simulation, optimization, and chaos run histories."""

    @staticmethod
    def record_run(
        run_id: str,
        architecture_id: str,
        run_type: str,
        result: Dict[str, Any],
        workload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        json_workload = json.dumps(workload or {})
        json_result = json.dumps(result)

        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO simulations (id, architecture_id, run_type, workload, result, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    architecture_id=excluded.architecture_id,
                    run_type=excluded.run_type,
                    workload=excluded.workload,
                    result=excluded.result,
                    created_at=excluded.created_at;
                """,
                (run_id, architecture_id, run_type, json_workload, json_result, now),
            )

        return {
            "id": run_id,
            "architecture_id": architecture_id,
            "run_type": run_type,
            "created_at": now,
        }

    @staticmethod
    def get_run(run_id: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT id, architecture_id, run_type, workload, result, created_at FROM simulations WHERE id = ?;",
                (run_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "architecture_id": row["architecture_id"],
                "run_type": row["run_type"],
                "workload": json.loads(row["workload"]),
                "result": json.loads(row["result"]),
                "created_at": row["created_at"],
            }

    @staticmethod
    def list_runs(
        architecture_id: Optional[str] = None,
        run_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = "SELECT id, architecture_id, run_type, created_at FROM simulations"
        params: List[Any] = []
        conditions: List[str] = []

        if architecture_id:
            conditions.append("architecture_id = ?")
            params.append(architecture_id)
        if run_type:
            conditions.append("run_type = ?")
            params.append(run_type)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ?;"
        params.append(limit)

        with get_db_connection() as conn:
            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "architecture_id": row["architecture_id"],
                    "run_type": row["run_type"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
