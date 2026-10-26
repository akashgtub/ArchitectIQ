# Member 2 Integration Specification & Shared Contract

**Document Version:** 1.0
**Schema Version:** 1.0
**Project:** ArchPilot AI — The Self-Testing System Design Agent
**Module Owners:**
- **Member 1:** Architecture Understanding, Image Extraction, Graph Validation, Baseline Orchestration, Root-Cause Investigation, Evidence-Based Handoff
- **Member 2:** Simulation Engine, Performance & Workload Modelling, Alternative Architecture Generation, Deterministic Optimization, Chaos/Failure Scenarios, Candidate Ranking

---

## A. Division of Responsibilities

### Member 1 Scope
* **Image Ingestion & Validation:** Secure handling of architecture diagrams (Pillow format, dimension, and byte validation).
* **Architecture Extraction:** Model-assisted extraction using Google Gemini / Gemma structured output, distinguishing directly observed facts, assumptions, and unknown variables.
* **Graph & Schema Validation:** NetworkX validation of endpoints, duplicate ID prevention, workload consistency ($R + W = 1.0$), and ambiguity detection.
* **Baseline Simulation Request:** Sending validated architectures and workloads to Member 2's simulator engine.
* **Root-Cause Investigation:** Generating hypotheses with controlled confidence categories (`low`, `medium`, `high`) and running allowlisted diagnostic experiments.
* **Optimization Handoff Generation:** Assembling a strictly validated `Member1Handoff` JSON payload.

### Member 2 Scope
* **Simulation Engine Implementation:** Real physics and performance simulation computing latency distributions, throughput bottlenecks, and resource utilization.
* **Alternative Architecture Synthesis:** Generating mutated architectural designs (e.g. read replicas, caching tiers, connection pooling, horizontal scaling).
* **Deterministic Optimization:** Evaluating candidate architectures against baseline measurements under identical workload conditions.
* **Chaos / Resilience Testing:** Injecting network partitions, worker failures, and latency spikes into candidate architectures.
* **Final Ranking:** Comparing candidate architectures across p95 latency, throughput, hourly cloud cost, and availability.

---

## B. Shared Data Contract (`backend/shared/schemas.py`)

Member 1 and Member 2 communicate strictly using the canonical Pydantic models defined in `backend/shared/schemas.py` (`schema_version: "1.0"`).

### 1. Key Pydantic Classes & Enums
* `ComponentType` (Enum): `api_server`, `web_server`, `load_balancer`, `database`, `cache`, `message_queue`, `object_storage`, `microservice`, `gateway`, `worker`, `cdn`, `external_service`, `unknown`
* `ConnectionType` (Enum): `request` (sync), `async_message` (queue/pubsub), `data_access` (persistence), `dependency` (logical/health), `stream` (websocket/kafka)
* `ConfidenceLabel` (Enum): `low`, `medium`, `high` (controlled descriptive labels; never uncalibrated floating-point probabilities)
* `HypothesisStatus` (Enum): `candidate`, `supported`, `tested_supported`, `confirmed`, `rejected`, `tested_weakened`, `inconclusive`, `insufficient_evidence`
* `SupportedDiagnosticExperiment` (Enum): `increase_workload`, `vary_read_write_mix`, `simulate_db_latency`, `scale_component`, `toggle_cache`, `isolate_dependency`
* `Component`: `{id: str, type: ComponentType, name: Optional[str], attributes: Dict[str, Any]}`
* `Connection`: `{source: str, target: str, type: ConnectionType, attributes: Dict[str, Any]}`
* `Workload`: `{requests_per_second: float (>0), read_ratio: float (0..1), write_ratio: float (0..1), peak_multiplier: Optional[float], concurrent_users: Optional[int]}`
* `Constraints`: `{max_p95_latency_ms: Optional[float], min_throughput_rps: Optional[float], max_cost_per_hour: Optional[float], min_availability: Optional[float]}`
* `Architecture`: `{schema_version: "1.0", architecture_id: str, components: List[Component], connections: List[Connection], workload: Workload, constraints: Constraints}`

---

## C. Member 2 Simulation Endpoints

Member 2 must expose two HTTP POST endpoints.

### 1. Baseline Simulation Endpoint
* **Path:** `POST /api/v1/simulate/baseline`
* **Consumes:** `BaselineSimulationRequest`
  ```json
  {
    "run_id": "base-inv-001",
    "architecture": { ... },
    "timeout_seconds": 30
  }
  ```
* **Produces:** `BaselineSimulationResponse` (HTTP 200)
  ```json
  {
    "run_id": "base-inv-001",
    "status": "completed",
    "source": "member2_simulator",
    "is_mock": false,
    "metrics": {
      "p95_latency_ms": 240.5,
      "throughput_rps": 1000.0,
      "cost_per_hour": 1.25,
      "availability": 0.999
    },
    "component_metrics": [
      {
        "component_id": "db-1",
        "cpu_utilization_pct": 85.0,
        "memory_utilization_pct": 60.0,
        "latency_p95_ms": 185.0,
        "throughput_rps": 400.0,
        "error_rate_pct": 0.0
      }
    ],
    "warnings": [
      "Database 'db-1' CPU utilization exceeded 80% threshold"
    ],
    "assumptions": [
      "Disk I/O latency modeled with 2000 provisioned IOPS"
    ],
    "simulator_version": "sim-v2.1.0"
  }
  ```

### 2. Diagnostic Simulation Endpoint
* **Path:** `POST /api/v1/simulate/diagnostic`
* **Consumes:** `DiagnosticExperimentRequest`
  ```json
  {
    "experiment_id": "exp-inv-001-01",
    "baseline_run_id": "base-inv-001",
    "experiment_type": "increase_workload",
    "target_components": ["db-1"],
    "parameters_to_change": {"multiplier": 1.5},
    "fixed_parameters": {"read_ratio": 0.8, "write_ratio": 0.2},
    "reason": "Test queue saturation on db-1 under 1.5x load",
    "hypotheses_tested": ["HYP-001"],
    "expected_evidence": "Disproportionate latency increase confirming database bottleneck"
  }
  ```
* **Produces:** `DiagnosticExperimentResponse` (HTTP 200)
  ```json
  {
    "experiment_id": "exp-inv-001-01",
    "baseline_run_id": "base-inv-001",
    "status": "completed",
    "source": "member2_simulator",
    "is_mock": false,
    "metrics": {
      "p95_latency_ms": 480.2,
      "throughput_rps": 1200.0,
      "cost_per_hour": 1.25,
      "availability": 0.975
    },
    "component_metrics": [],
    "diff_from_baseline": [
      {
        "metric_name": "p95_latency_ms",
        "baseline_value": 240.5,
        "diagnostic_value": 480.2,
        "diff_value": 239.7,
        "diff_pct": 99.7,
        "unit": "ms",
        "interpretation": "1.5x load caused 99.7% spike in p95 latency, confirming queuing on db-1"
      }
    ],
    "warnings": [],
    "simulator_version": "sim-v2.1.0"
  }
  ```

---

## D. Member 1 Endpoints

Member 2 (and the UI) can call Member 1's implemented REST routes:

| HTTP Method | Endpoint | Description | Request Body | Response Body |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/architecture/analyze` | Ingests diagram image and requirements | `multipart/form-data`: `image`, `requirements`, `workload_json`, `constraints_json` | `ArchitectureAnalyzeResponse` |
| `POST` | `/api/v1/investigations` | Initiates simulation and root cause analysis | `StartInvestigationRequest` | `InvestigationDetailResponse` (HTTP 201) |
| `GET` | `/api/v1/investigations/{id}` | Checks status of ongoing or completed investigation | None | `InvestigationDetailResponse` |
| `GET` | `/api/v1/investigations/{id}/handoff`| Retrieves final validated optimization handoff | None | `Member1Handoff` |
| `GET` | `/health` or `/api/v1/health` | Health checks and schema version | None | `{status: "healthy", schema_version: "1.0"}` |

---

## E. Metric Definitions & Measurement Standards

All metric fields must adhere strictly to these units and definitions:

| Metric Name | Type | Unit | Meaning |
| :--- | :--- | :--- | :--- |
| `p95_latency_ms` | `float` | `ms` | 95th percentile end-to-end client round-trip latency. |
| `throughput_rps` | `float` | `rps` | Successfully processed requests per second. |
| `cost_per_hour` | `float` | `USD/hr` | Estimated cloud infrastructure operational cost per hour. |
| `availability` | `float` | `ratio` | Fraction of requests succeeding without 5xx errors ($0.0$ to $1.0$). |
| `cpu_utilization_pct` | `float` | `%` | Component-level CPU utilization ($0.0$ to $100.0\%$). |
| `memory_utilization_pct`| `float` | `%` | Component-level memory footprint ($0.0$ to $100.0\%$). |
| `error_rate_pct` | `float` | `%` | Percentage of failed or timed-out requests ($0.0$ to $100.0\%$). |

> **Rule:** If Member 2's simulator does not yet calculate a specific metric, it must be returned as `null` (`None`). It must **never** be fabricated or defaulted to `0.0`.

---

## F. Baseline Workload & Constraint Preservation

When Member 2 synthesizes candidate architectures:
1. **Preserve Workload Conditions:** The candidate must be simulated under the exact same `requests_per_second`, `read_ratio`, and `write_ratio` as the baseline.
2. **Preserve Hard Constraints:** `handoff.optimization_handoff.hard_constraints` must all be satisfied:
   - If `max_p95_latency_ms` is specified, any candidate with $p95 > \text{constraint}$ is disqualified.
   - If `max_cost_per_hour` is specified, candidate cost cannot exceed this limit.
3. **Preserve Documented Assumptions:** All items in `handoff.optimization_handoff.assumptions_to_preserve` (e.g. provisioned IOPS, inter-zone network delay) must remain fixed.

---

## G. Local Integration Instructions

### Step 1: Start Member 1 Engine
```bash
# Terminal 1
cd ArchitectIQ
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 2: Configure Member 2 Simulator URL
When Member 2 starts their simulation engine on port 8001:
```bash
# In .env:
SIMULATOR_BASE_URL=http://localhost:8001
USE_MOCK_SIMULATOR=false
```

### Step 3: Trigger an Investigation
```bash
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{
    "architecture": {
      "schema_version": "1.0",
      "architecture_id": "arch-integration-001",
      "components": [
        {"id": "api-1", "type": "api_server", "attributes": {"cpu_cores": 2}},
        {"id": "db-1", "type": "database", "attributes": {"cpu_cores": 2}}
      ],
      "connections": [
        {"source": "api-1", "target": "db-1", "type": "data_access"}
      ],
      "workload": {
        "requests_per_second": 1000.0,
        "read_ratio": 0.8,
        "write_ratio": 0.2
      },
      "constraints": {
        "max_p95_latency_ms": 200.0
      }
    },
    "max_diagnostic_experiments": 3,
    "timeout_seconds": 60
  }'
```

### Step 4: Fetch Handoff
```bash
curl http://localhost:8000/api/v1/investigations/{investigation_id}/handoff
```

In Python:
```python
import httpx
from backend.shared.schemas import Member1Handoff

resp = httpx.get("http://localhost:8000/api/v1/investigations/inv-sample/handoff")
handoff: Member1Handoff = Member1Handoff.model_validate(resp.json())
print(f"Status: {handoff.status}")
print(f"Target Components to Optimize: {handoff.optimization_handoff.recommended_targets}")
print(f"Hard Constraints: {handoff.optimization_handoff.hard_constraints}")
```

---

## H. Integration Acceptance Criteria for Member 2

To achieve complete system integration, Member 2's implementation must satisfy:
1. **Schema Adherence:** Request and response bodies on `/api/v1/simulate/baseline` and `/api/v1/simulate/diagnostic` must parse against `BaselineSimulationResponse` and `DiagnosticExperimentResponse`.
2. **Preserve Run ID:** Responses must return the exact `run_id` and `baseline_run_id` provided in requests.
3. **Allowlist Compliance:** Diagnostic endpoint must support the six allowlisted experiment types:
   - `increase_workload`
   - `vary_read_write_mix`
   - `simulate_db_latency`
   - `scale_component`
   - `toggle_cache`
   - `isolate_dependency`
4. **Authentic Metrics:** Return actual measurements with clear `is_mock: false` and `source: "member2_simulator"` labels.
5. **Truthful Missing Values:** Set unsupported metrics to `null` rather than generating placeholder numbers.
6. **Graceful Error Handling:** Return HTTP 400 for malformed architecture models, HTTP 504 for internal timeouts, and standard `{error_code, message}` bodies.
