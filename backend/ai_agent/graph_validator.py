"""
ArchPilot AI - Architecture Graph Validator
Member 1: Architecture Understanding & Root-Cause Investigation

Performs rigorous structural, workload, and semantic validation of architecture graphs
using NetworkX and Pydantic rules.
Surfaces ambiguities without hallucinating or making silent assumptions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set, Tuple
import networkx as nx

from backend.shared.schemas import (
    Architecture,
    ArchitectureValidationResult,
    ClarificationQuestion,
    Component,
    ComponentType,
    Connection,
    ConnectionType,
    ValidationIssue,
    ValidationSeverity,
    Workload,
)

logger = logging.getLogger("archpilot.graph_validator")


class GraphValidator:
    """
    Validates structural topology, component attributes, and workload parameters.
    """

    def validate_architecture(
        self,
        arch_data: Dict[str, Any],
        raw_clarifications: Optional[List[Dict[str, Any]]] = None,
        raw_assumptions: Optional[List[str]] = None,
    ) -> ArchitectureValidationResult:
        """
        Validates raw dictionary or parsed Architecture data.
        Returns ArchitectureValidationResult with valid flag, issues, assumptions, and questions.
        """
        issues: List[ValidationIssue] = []
        assumptions: List[str] = list(raw_assumptions or [])
        clarification_questions: List[ClarificationQuestion] = []

        # Parse raw clarification questions if provided
        if raw_clarifications:
            for q_data in raw_clarifications:
                try:
                    clarification_questions.append(ClarificationQuestion(**q_data))
                except Exception as e:
                    logger.debug("Skipping unparseable clarification question: %s", e)

        # 1. Component validation & ID uniqueness
        components_raw = arch_data.get("components", [])
        seen_ids: Set[str] = set()
        duplicate_ids: Set[str] = set()
        valid_components: List[Dict[str, Any]] = []

        if not components_raw:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="ERR_EMPTY_COMPONENTS",
                    message="Architecture must contain at least one component.",
                    affected_components=[],
                    requires_clarification=True,
                )
            )

        for comp in components_raw:
            comp_id = str(comp.get("id", "")).strip()
            if not comp_id:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="ERR_EMPTY_COMPONENT_ID",
                        message="A component has an empty or missing 'id'.",
                        affected_components=[],
                        requires_clarification=False,
                    )
                )
                continue

            if comp_id in seen_ids:
                duplicate_ids.add(comp_id)
            else:
                seen_ids.add(comp_id)

            # Validate component type
            raw_type = comp.get("type", "")
            try:
                ComponentType(raw_type)
            except ValueError:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="WARN_UNKNOWN_COMPONENT_TYPE",
                        message=f"Component '{comp_id}' has unrecognized type '{raw_type}'. Defaulting to 'unknown'.",
                        affected_components=[comp_id],
                        requires_clarification=False,
                    )
                )
                comp["type"] = ComponentType.UNKNOWN.value

            valid_components.append(comp)

        if duplicate_ids:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="ERR_DUPLICATE_COMPONENT_ID",
                    message=f"Duplicate component IDs found: {', '.join(sorted(duplicate_ids))}.",
                    affected_components=list(duplicate_ids),
                    requires_clarification=False,
                )
            )

        # 2. Connection validation & Endpoint existence
        connections_raw = arch_data.get("connections", [])
        graph = nx.DiGraph()
        for cid in seen_ids:
            graph.add_node(cid)

        seen_edges: Set[Tuple[str, str]] = set()

        for conn in connections_raw:
            src = str(conn.get("source", "")).strip()
            tgt = str(conn.get("target", "")).strip()

            if not src or not tgt:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="ERR_INVALID_CONNECTION_ENDPOINT",
                        message="Connection endpoint source or target is empty.",
                        affected_components=[c for c in (src, tgt) if c],
                        requires_clarification=False,
                    )
                )
                continue

            # Check existence of endpoints
            missing_endpoints = []
            if src not in seen_ids:
                missing_endpoints.append(src)
            if tgt not in seen_ids:
                missing_endpoints.append(tgt)

            if missing_endpoints:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="ERR_NONEXISTENT_ENDPOINT",
                        message=f"Connection references non-existent component(s): {', '.join(missing_endpoints)} (source='{src}', target='{tgt}').",
                        affected_components=missing_endpoints,
                        requires_clarification=True,
                    )
                )
                continue

            # Check self-loops
            if src == tgt:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="WARN_SELF_LOOP",
                        message=f"Component '{src}' has a connection to itself.",
                        affected_components=[src],
                        requires_clarification=False,
                    )
                )

            # Check duplicate edges
            edge_key = (src, tgt)
            if edge_key in seen_edges:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        code="INFO_DUPLICATE_EDGE",
                        message=f"Multiple connections defined between '{src}' and '{tgt}'.",
                        affected_components=[src, tgt],
                        requires_clarification=False,
                    )
                )
            seen_edges.add(edge_key)

            # Add edge to NetworkX graph
            graph.add_edge(src, tgt, **conn.get("attributes", {}))

        # 3. Topology Analysis with NetworkX
        # Disconnected components (0 in-degree and 0 out-degree)
        isolated_nodes = list(nx.isolates(graph))
        if isolated_nodes:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    code="WARN_ISOLATED_COMPONENTS",
                    message=f"Found isolated component(s) with no connections: {', '.join(isolated_nodes)}. Verify if missing in diagram.",
                    affected_components=isolated_nodes,
                    requires_clarification=False,
                )
            )

        # Cycle detection: Real architectures can have feedback loops or polling,
        # but synchronous request cycles can indicate deadlock or infinite recursion.
        try:
            cycles = list(nx.simple_cycles(graph))
            if cycles:
                cycle_strs = [" -> ".join(c + [c[0]]) for c in cycles]
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        code="INFO_DETECTED_CYCLES",
                        message=f"Detected cyclical connection paths: {'; '.join(cycle_strs)}. Ensure async or bounded.",
                        affected_components=list({node for c in cycles for node in c}),
                        requires_clarification=False,
                    )
                )
        except Exception as e:
            logger.debug("Cycle check skipped or encountered error: %s", e)

        # 4. Workload Validation
        workload_raw = arch_data.get("workload")
        if not workload_raw:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="ERR_MISSING_WORKLOAD",
                    message="Architecture specification is missing required 'workload' configuration.",
                    affected_components=[],
                    requires_clarification=True,
                )
            )
            clarification_questions.append(
                ClarificationQuestion(
                    question_id="Q-WORKLOAD-MISSING",
                    question="What is the expected request rate (requests per second) and read/write ratio?",
                    affected_components=[],
                    category="workload",
                    suggested_options=["1,000 RPS (80% read / 20% write)", "5,000 RPS (90% read / 10% write)", "10,000 RPS (50% read / 50% write)"]
                )
            )
        else:
            try:
                rps = float(workload_raw.get("requests_per_second", -1))
                if rps <= 0:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="ERR_INVALID_WORKLOAD_RPS",
                            message=f"Workload 'requests_per_second' must be greater than 0 (got {rps}).",
                            affected_components=[],
                            requires_clarification=True,
                        )
                    )

                read_r = float(workload_raw.get("read_ratio", -1))
                write_r = float(workload_raw.get("write_ratio", -1))
                if read_r < 0 or read_r > 1.0 or write_r < 0 or write_r > 1.0:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="ERR_INVALID_RATIO_RANGE",
                            message="Workload 'read_ratio' and 'write_ratio' must both be between 0.0 and 1.0.",
                            affected_components=[],
                            requires_clarification=True,
                        )
                    )
                else:
                    sum_ratios = read_r + write_r
                    if not (0.99 <= sum_ratios <= 1.01):
                        issues.append(
                            ValidationIssue(
                                severity=ValidationSeverity.ERROR,
                                code="ERR_INCONSISTENT_RATIOS",
                                message=f"Read ratio ({read_r}) and write ratio ({write_r}) must sum to 1.0 (got {sum_ratios:.2f}).",
                                affected_components=[],
                                requires_clarification=True,
                            )
                        )
            except (ValueError, TypeError) as ex:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="ERR_MALFORMED_WORKLOAD_VALUES",
                        message=f"Workload parameters contain non-numeric or invalid values: {ex}",
                        affected_components=[],
                        requires_clarification=True,
                    )
                )

        # 5. Component Semantic Checks
        # E.g. Check database without attributes
        for comp in valid_components:
            cid = comp.get("id")
            ctype = comp.get("type")
            attrs = comp.get("attributes", {})
            if ctype == ComponentType.DATABASE.value and not attrs.get("engine"):
                assumptions.append(f"Database '{cid}' did not specify DB engine; assuming relational SQL database.")
            if ctype == ComponentType.CACHE.value and not attrs.get("capacity_mb"):
                assumptions.append(f"Cache '{cid}' did not specify capacity; assuming standard 2GB in-memory cache.")

        # Determine validity: valid if NO issues with severity == ERROR
        has_blocking_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
        is_valid = not has_blocking_errors

        return ArchitectureValidationResult(
            valid=is_valid,
            issues=issues,
            assumptions=assumptions,
            unresolved_questions=clarification_questions,
        )
