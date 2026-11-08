"""
Tests for Graph Validator
Covers:
- Case 3: Duplicate component IDs.
- Case 4: Connection referencing a nonexistent component.
- Case 5: Missing workload fields.
- Case 6: Invalid workload ranges.
- Disconnected components and cycle handling.
"""

import pytest

from backend.ai_agent.graph_validator import GraphValidator
from backend.shared.schemas import ValidationSeverity


def test_case_3_duplicate_component_ids():
    """Case 3: Duplicate component IDs must be flagged as ERR_DUPLICATE_COMPONENT_ID and fail validation."""
    validator = GraphValidator()
    arch_data = {
        "architecture_id": "arch-dup-test",
        "components": [
            {"id": "api-1", "type": "api_server"},
            {"id": "api-1", "type": "api_server"},  # Duplicate!
            {"id": "db-1", "type": "database"},
        ],
        "connections": [
            {"source": "api-1", "target": "db-1", "type": "request"}
        ],
        "workload": {
            "requests_per_second": 500,
            "read_ratio": 0.8,
            "write_ratio": 0.2
        }
    }

    result = validator.validate_architecture(arch_data)
    assert result.valid is False
    codes = [issue.code for issue in result.issues]
    assert "ERR_DUPLICATE_COMPONENT_ID" in codes
    dup_issue = next(issue for issue in result.issues if issue.code == "ERR_DUPLICATE_COMPONENT_ID")
    assert "api-1" in dup_issue.affected_components


def test_case_4_connection_referencing_nonexistent_component():
    """Case 4: Connection referencing a nonexistent component must be flagged as ERR_NONEXISTENT_ENDPOINT."""
    validator = GraphValidator()
    arch_data = {
        "architecture_id": "arch-missing-endpoint",
        "components": [
            {"id": "api-1", "type": "api_server"},
        ],
        "connections": [
            {"source": "api-1", "target": "ghost-db", "type": "request"}  # ghost-db doesn't exist!
        ],
        "workload": {
            "requests_per_second": 500,
            "read_ratio": 0.8,
            "write_ratio": 0.2
        }
    }

    result = validator.validate_architecture(arch_data)
    assert result.valid is False
    codes = [issue.code for issue in result.issues]
    assert "ERR_NONEXISTENT_ENDPOINT" in codes
    missing_issue = next(issue for issue in result.issues if issue.code == "ERR_NONEXISTENT_ENDPOINT")
    assert "ghost-db" in missing_issue.affected_components
    assert missing_issue.requires_clarification is True


def test_case_5_missing_workload_fields():
    """Case 5: Missing workload fields must be caught and clarification requested."""
    validator = GraphValidator()
    arch_data = {
        "architecture_id": "arch-no-workload",
        "components": [
            {"id": "api-1", "type": "api_server"},
            {"id": "db-1", "type": "database"},
        ],
        "connections": [
            {"source": "api-1", "target": "db-1", "type": "request"}
        ],
        # "workload" is missing!
    }

    result = validator.validate_architecture(arch_data)
    assert result.valid is False
    codes = [issue.code for issue in result.issues]
    assert "ERR_MISSING_WORKLOAD" in codes
    assert len(result.unresolved_questions) > 0
    assert result.unresolved_questions[0].category == "workload"


def test_case_6_invalid_workload_ranges():
    """Case 6: Invalid workload ranges (negative RPS, bad ratio sums)."""
    validator = GraphValidator()

    # Subcase A: Negative requests_per_second
    bad_rps_data = {
        "architecture_id": "arch-neg-rps",
        "components": [{"id": "api-1", "type": "api_server"}],
        "connections": [],
        "workload": {
            "requests_per_second": -100,  # Invalid!
            "read_ratio": 0.8,
            "write_ratio": 0.2
        }
    }
    res_a = validator.validate_architecture(bad_rps_data)
    assert res_a.valid is False
    assert any(i.code == "ERR_INVALID_WORKLOAD_RPS" for i in res_a.issues)

    # Subcase B: Ratios sum to 1.5 instead of 1.0
    bad_ratio_sum = {
        "architecture_id": "arch-bad-ratio-sum",
        "components": [{"id": "api-1", "type": "api_server"}],
        "connections": [],
        "workload": {
            "requests_per_second": 500,
            "read_ratio": 0.8,
            "write_ratio": 0.7  # Sum is 1.5!
        }
    }
    res_b = validator.validate_architecture(bad_ratio_sum)
    assert res_b.valid is False
    assert any(i.code == "ERR_INCONSISTENT_RATIOS" for i in res_b.issues)

    # Subcase C: Ratio greater than 1.0
    bad_ratio_val = {
        "architecture_id": "arch-bad-ratio-val",
        "components": [{"id": "api-1", "type": "api_server"}],
        "connections": [],
        "workload": {
            "requests_per_second": 500,
            "read_ratio": 1.5,
            "write_ratio": -0.5
        }
    }
    res_c = validator.validate_architecture(bad_ratio_val)
    assert res_c.valid is False
    assert any(i.code == "ERR_INVALID_RATIO_RANGE" for i in res_c.issues)


def test_disconnected_components_warning_only():
    """Disconnected components produce a warning, but do NOT make architecture invalid."""
    validator = GraphValidator()
    arch_data = {
        "architecture_id": "arch-isolated",
        "components": [
            {"id": "api-1", "type": "api_server"},
            {"id": "db-1", "type": "database"},
            {"id": "standalone-worker", "type": "worker"},  # No connections
        ],
        "connections": [
            {"source": "api-1", "target": "db-1", "type": "request"}
        ],
        "workload": {
            "requests_per_second": 500,
            "read_ratio": 0.8,
            "write_ratio": 0.2
        }
    }

    result = validator.validate_architecture(arch_data)
    # Still valid because isolated component is a warning, not a hard error
    assert result.valid is True
    warn = next((i for i in result.issues if i.code == "WARN_ISOLATED_COMPONENTS"), None)
    assert warn is not None
    assert "standalone-worker" in warn.affected_components
