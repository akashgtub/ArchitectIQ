# ArchitectIQ — Provisional Integration Contract (Feature 1 & Feature 2)

**Author:** Member 2 (Backend Simulation & Optimization Architect)  
**Status:** Provisional (Draft for Parallel Development)  
**Target:** Integration with Member 1 (AI Diagram Extraction, Validation & Root-Cause Analysis)

---

## 1. Overview and Purpose

This document defines the data contract and operational semantics between:
- **Member 1 (Producer):** AI architecture diagram extraction, graph parser, topology validator, and root-cause investigator.
- **Member 2 (Consumer / Engine):** Workload generation, discrete queueing performance simulation, bottleneck diagnosis, candidate architecture optimization, and chaos resilience testing.

The numerical simulation engine operates **deterministically** without requiring LLM calls during simulation runs. All metrics are derived from verified mathematical queueing models and discrete-event traces.

---

## 2. Shared Architecture Schema

### 2.1 JSON Architecture Representation

```json
{
  "components": [
    {
      "id": "lb-1",
      "type": "load_balancer",
      "name": "Public Ingress LB",
      "capacity_rps": 2000.0,
      "replicas": 1,
      "base_latency_ms": 1.5,
      "cost_per_month_usd": 25.0
    },
    {
      "id": "api-1",
      "type": "api_server",
      "name": "Core REST API",
      "capacity_rps": 400.0,
      "replicas": 3,
      "base_latency_ms": 12.0,
      "cost_per_month_usd": 40.0
    },
    {
      "id": "cache-1",
      "type": "cache",
      "name": "Redis Distributed Cache",
      "capacity_rps": 3000.0,
      "replicas": 1,
      "base_latency_ms": 2.0,
      "cache_hit_ratio": 0.85,
      "cost_per_month_usd": 60.0
    },
    {
      "id": "db-1",
      "type": "database",
      "name": "Primary PostgreSQL DB",
      "capacity_rps": 500.0,
      "replicas": 1,
      "base_latency_ms": 25.0,
      "cost_per_month_usd": 150.0
    }
  ],
  "connections": [
    {
      "source": "lb-1",
      "target": "api-1",
      "protocol": "http",
      "latency_overhead_ms": 1.0,
      "path_type": "both"
    },
    {
      "source": "api-1",
      "target": "cache-1",
      "protocol": "redis",
      "latency_overhead_ms": 0.5,
      "path_type": "read"
    },
    {
      "source": "api-1",
      "target": "db-1",
      "protocol": "sql",
      "latency_overhead_ms": 1.5,
      "path_type": "write"
    },
    {
      "source": "cache-1",
      "target": "db-1",
      "protocol": "sql",
      "latency_overhead_ms": 1.0,
      "path_type": "read"
    }
  ]
}
```

---

## 3. Detailed Field Specifications and Units

### 3.1 Component Fields

| Field Name | Type | Required? | Default | Unit | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `string` | **Yes** | — | — | Unique identifier (e.g., `"api-1"`, `"cache-1"`). |
| `type` | `string` | **Yes** | — | — | One of: `load_balancer`, `api_server`, `cache`, `database`, `message_broker`, `queue`, `third_party_service`, `storage`. |
| `name` | `string` | No | `null` | — | Human-readable label for UI visualization. |
| `capacity_rps` | `float` | **Yes** | — | Requests / Sec | Peak processing rate for a **single replica** before saturation. Must be `> 0`. |
| `replicas` | `integer` | No | `1` | Instances | **Total active instances** of this component. Total effective capacity = `capacity_rps * replicas`. Must be `>= 1`. |
| `base_latency_ms` | `float` | No | `5.0` | Milliseconds | Processing time at zero/low load (excluding queue wait & network overhead). Must be `>= 0`. |
| `cost_per_month_usd`| `float` | No | *Tier Default* | USD ($) | Running cost per replica per month. If `0.0`, default pricing tier applies. |
| `cache_hit_ratio` | `float` | Conditional | `0.8` (if cache)| Fraction (0.0–1.0) | Applicable when `type == "cache"`. Fraction of read traffic satisfied by cache. |
| `max_queue_size` | `integer` | No | `1000` | Requests | Maximum queue depth before requests are dropped (error rate increases). |
| `metadata` | `object` | No | `{}` | Key-Value | Extension bucket for Member 1's extracted bounding boxes, notes, or tags. |

### 3.2 Connection Fields

| Field Name | Type | Required? | Default | Unit | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `source` | `string` | **Yes** | — | — | Origin component `id`. Must exist in `components`. |
| `target` | `string` | **Yes** | — | — | Destination component `id`. Must exist in `components`. |
| `protocol` | `string` | No | `"http"` | — | Network protocol (`"http"`, `"grpc"`, `"redis"`, `"sql"`, etc.). |
| `latency_overhead_ms`| `float` | No | `1.0` | Milliseconds | Transport and serialization network latency per hop. |
| `path_type` | `string` | No | `"both"` | — | Traffic path: `"both"`, `"read"`, or `"write"`. |

### 3.3 Workload Configuration Fields

```json
{
  "requests_per_second": 800.0,
  "read_ratio": 0.8,
  "duration_seconds": 60.0,
  "pattern": "constant",
  "burst_multiplier": 2.0,
  "burst_start_sec": 20.0,
  "burst_duration_sec": 10.0,
  "seed": 42,
  "step_size_sec": 1.0
}
```

- `requests_per_second` (`float > 0`): Base arrival rate (RPS).
- `read_ratio` (`0.0 <= float <= 1.0`): Fraction of total traffic representing read operations (write ratio = `1.0 - read_ratio`).
- `pattern` (`string`): One of `"constant"`, `"ramp_up"`, `"burst"`, `"spike"`.
- `seed` (`integer`): Reproducible pseudo-random seed for stochastic distribution.

---

## 4. Operational and Simulation Semantics

### 4.1 Replica-Count Semantics
- The `replicas` attribute represents the **total active instances running concurrently**.
- A component with `capacity_rps: 400` and `replicas: 3` has a total system capacity of `1200 RPS`.
- When an API server scales out, incoming load is assumed to be evenly balanced across replicas.
- Monthly infrastructure cost scales linearly: `total_cost = replicas * cost_per_month_usd`.

### 4.2 Cache-Aside Semantics
- When an architecture includes a `cache` component:
  1. Incoming `read` traffic routes to the cache.
  2. Cache hits (`read_traffic * cache_hit_ratio`) complete at the cache with `base_latency_ms`.
  3. Cache misses (`read_traffic * (1 - cache_hit_ratio)`) continue down to the connected database.
  4. `write` traffic bypasses cache reads and is routed to the database (write path), incurring database write processing.

### 4.3 Routing and Graph Execution
- Entry-point components (in-degree zero or marked `load_balancer`/`api_server`) receive initial workload traffic.
- Traffic flows through outgoing directed connections.
- Hop-by-hop latency is accumulated:
  $$\text{Hop Latency} = \text{base\_latency\_ms} + \text{queue\_wait\_ms} + \text{latency\_overhead\_ms}$$
- Percentile latencies ($p50, p95, p99$) are computed from simulated request observations across the discrete time horizon.

---

## 5. Service Functions for Member 1 Integration

Member 1 can invoke Member 2's capabilities directly via clean Python service functions or REST API endpoints:

```python
from backend.api.service import run_simulation, optimize_architecture, simulate_failure

# 1. Baseline Simulation
result = run_simulation(architecture_dict, workload_dict, constraints_dict)

# 2. Architecture Optimization
opt_result = optimize_architecture(
    architecture=architecture_dict,
    workload=workload_dict,
    constraints=constraints_dict,
    objective="balanced",
    max_candidates=8
)

# 3. Chaos Resilience Simulation
chaos_result = simulate_failure(
    architecture=architecture_dict,
    workload=workload_dict,
    scenario=scenario_dict
)
```

---

## 6. Schema Reconciliation Guidelines for Member 1

When Member 1 finalizes their AI diagram extraction models:
1. Ensure all extracted components contain unique `id` strings.
2. If Member 1's extractor cannot determine `capacity_rps`, standard sensible defaults based on component type will be applied automatically.
3. Extra attributes extracted by Member 1 (e.g., bounding boxes, visual coordinates, cloud provider tags) will be preserved in `metadata`.
4. The schema uses Pydantic v2 `ConfigDict(extra="ignore")` so additional fields added by Member 1 will not break simulation.
