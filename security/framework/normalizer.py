"""
ArchitectIQ DevSecOps - Standard Security Report Normalizer
Enforces identical schema across all 12 security gates.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class SecurityGateReport:
    """Standardized report model for all 12 security gates."""

    def __init__(
        self,
        gate_id: str,
        gate_name: str,
        tool_name: str,
        tool_version: str,
        execution_status: str,  # PASS, FAIL, BLOCKED, NOT RUN, PARTIAL
        severity_verdict: str,  # PASS, FAIL, WARNING, BLOCKED
        finding_counts: Optional[Dict[str, int]] = None,
        quality_gate_thresholds: Optional[Dict[str, int]] = None,
        findings: Optional[List[Dict[str, Any]]] = None,
        report_location: str = "",
        execution_duration_sec: float = 0.0,
        error_information: Optional[str] = None,
        timestamp: Optional[str] = None,
    ):
        self.gate_id = gate_id
        self.gate_name = gate_name
        self.tool_name = tool_name
        self.tool_version = tool_version
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.execution_status = execution_status
        self.severity_verdict = severity_verdict
        self.finding_counts = finding_counts or {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        self.quality_gate_thresholds = quality_gate_thresholds or {
            "max_allowed_critical": 0,
            "max_allowed_high": 0,
            "max_allowed_medium": 10,
        }
        self.findings = findings or []
        self.report_location = report_location
        self.execution_duration_sec = round(execution_duration_sec, 2)
        self.error_information = error_information

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "gate_name": self.gate_name,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "timestamp": self.timestamp,
            "execution_status": self.execution_status,
            "severity_verdict": self.severity_verdict,
            "finding_counts": self.finding_counts,
            "quality_gate_thresholds": self.quality_gate_thresholds,
            "findings": self.findings,
            "report_location": self.report_location,
            "execution_duration_sec": self.execution_duration_sec,
            "error_information": self.error_information,
        }

    def write_json(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return output_path

    @classmethod
    def load_json(cls, file_path: Path) -> "SecurityGateReport":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            gate_id=data["gate_id"],
            gate_name=data["gate_name"],
            tool_name=data["tool_name"],
            tool_version=data.get("tool_version", "unknown"),
            execution_status=data["execution_status"],
            severity_verdict=data["severity_verdict"],
            finding_counts=data.get("finding_counts"),
            quality_gate_thresholds=data.get("quality_gate_thresholds"),
            findings=data.get("findings"),
            report_location=data.get("report_location", str(file_path)),
            execution_duration_sec=data.get("execution_duration_sec", 0.0),
            error_information=data.get("error_information"),
            timestamp=data.get("timestamp"),
        )

