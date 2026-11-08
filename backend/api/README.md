# ArchitectIQ — Backend API & Integration Guide (Feature 2)

**Author:** Member 2 (Backend Simulation & Optimization Architect)  
**Status:** Feature Complete & Production-Ready for Integration  
**Target:** Integration with Member 1 (AI Diagram Extraction, Topology Validation & Frontend)

---

## 1. Overview

This module exposes the discrete-event simulation engine, candidate architecture optimizer, and chaos engineering lab via:
1. **Python Service Facade** (`backend.api.service`): Direct, in-process, zero-network-overhead function calls.
2. **Standalone FastAPI Router** (`backend.api.routes`): HTTP REST endpoints ready to mount into the main application.

Numerical simulations are **deterministic**, verified by mathematical queueing models, and completely independent of external LLM APIs.

---

## 2. Mounting the Router in FastAPI

Member 1 or the application integration owner can mount the router with two lines of code without modifying internal modules:

```python
from fastapi import FastAPI
from backend.api.routes import router as simulation_router

app = FastAPI(title="ArchitectIQ API", version="1.0.0")

# Mount Member 2's simulation, optimization, and chaos lab endpoints
app.include_router(simulation_router)
```

The router automatically registers all routes under the `/api` prefix with interactive Swagger documentation at `/docs`.

---

## 3. Available Endpoints

### 3.1 `POST /api/simulation/run`

Simulates discrete request flow across the architecture graph under the given workload and reports latency percentiles, throughput, error rate, queueing, and bottlenecks.

#### Request Example

```json
{
  "architecture": {
    "components": [
      {
        "id": "lb-1",
        "type": "load_balancer",
        "capacity_rps": 2000.0,
        "replicas": 1,
        "base_latency_ms": 1.5,
        "cost_per_month_usd": 25.0
      },
      {
        "id": "api-1",
        "type": "api_server",
        "capacity_rps": 400.0,
        "replicas": 2,
        "base_latency_ms": 10.0,
        "cost_per_month_usd": 40.0
      },
      {
        "id": "cache-1",
        "type": "cache",
        "capacity_rps": 2500.0,
        "replicas": 1,
        "base_latency_ms": 2.0,
        "cache_hit_ratio": 0.85,
        "cost_per_month_usd": 60.0
      },
      {
        "id": "db-1",
        "type": "database",
        "capacity_rps": 600.0,
        "replicas": 1,
        "base_latency_ms": 25.0,
        "cost_per_month_usd": 150.0
      }
    ],
    "connections": [
      {"source": "lb-1", "target": "api-1", "path_type": "both"},
      {"source": "api-1", "target": "cache-1", "path_type": "read"},
      {"source": "api-1", "target": "db-1", "path_type": "write"},
      {"source": "cache-1", "target": "db-1", "path_type": "read"}
    ]
  },
  "workload": {
    "requests_per_second": 500.0,
    "read_ratio": 0.8,
    "duration_seconds": 30.0,
    "pattern": "constant",
    "seed": 42
  },
  "constraints": {
    "max_p95_latency_ms": 150.0,
    "monthly_budget_usd": 500.0,
    "min_throughput_rps": 450.0,
    "max_error_rate": 0.05
  }
}
```

#### Response Example (200 OK)

```json
{
  "status": "success",
  "simulation_type": "baseline",
  "metrics": {
    "mean_latency_ms": 24.52,
    "p50_latency_ms": 15.40,
    "p95_latency_ms": 47.12,
    "p99_latency_ms": 47.12,
    "throughput_rps": 501.2,
    "error_rate": 0.0,
    "completed_requests": 15036,
    "dropped_requests": 0,
    "total_monthly_cost_usd": 315.0,
    "component_breakdown": {
      "lb-1": {
        "component_id": "lb-1",
        "component_type": "load_balancer",
        "replicas": 1,
        "effective_capacity_rps": 2000.0,
        "offered_rps": 501.2,
        "throughput_rps": 501.2,
        "dropped_rps": 0.0,
        "utilization": 0.2506,
        "mean_queue_depth": 0.0,
        "mean_service_time_ms": 1.5,
        "mean_queue_time_ms": 0.03,
        "total_latency_ms": 1.53,
        "is_bottleneck": false,
        "cost_per_month_usd": 25.0
      }
    }
  },
  "bottlenecks": [],
  "constraint_violations": [],
  "assumptions": [
    "Cache-aside pattern: read traffic queries cache first with probability 'cache_hit_ratio' completing at cache; cache misses and write traffic route to downstream database.",
    "Replica scaling: total component throughput capacity equals single-replica capacity multiplied by replica count (capacity_rps * replicas).",
    "Routing: incoming traffic is uniformly distributed across available downstream replicas and eligible connections.",
    "Queueing model: M/M/c queueing approximation applied for wait times below saturation; requests exceeding max_queue_size are dropped.",
    "Network overhead: per-hop transmission and serialization latency applied from connection definitions."
  ],
  "simulation_metadata": {
    "method": "discrete_event_queueing",
    "seed": 42,
    "total_simulated_requests": 15036,
    "duration_seconds": 30.0,
    "pattern": "constant"
  }
}
```

---

### 3.2 `POST /api/optimization/run`

Explores valid architecture variations (API replica scaling, database tier upgrade, cache hit-rate tuning, composite topologies), evaluates each under identical workload conditions, enforces hard constraints, and ranks feasible candidates against the target objective.

#### Request Example

```json
{
  "architecture": { ... },
  "workload": {
    "requests_per_second": 750.0,
    "read_ratio": 0.8,
    "duration_seconds": 30.0,
    "seed": 42
  },
  "constraints": {
    "max_p95_latency_ms": 180.0,
    "monthly_budget_usd": 500.0,
    "min_throughput_rps": 700.0,
    "max_error_rate": 0.05
  },
  "objective": "balanced",
  "max_candidates": 8
}
```

Supported objectives:
- `"minimize_latency"`: Minimizes $p95$ latency among feasible candidates.
- `"minimize_cost"`: Minimizes monthly cloud cost among feasible candidates.
- `"maximize_throughput"`: Maximizes completed requests per second.
- `"balanced"`: Normalized multi-criteria score ($0.35 \times \text{latency} + 0.30 \times \text{cost} + 0.20 \times \text{throughput} + 0.15 \times \text{error}$).

#### Response Highlights (200 OK)

```json
{
  "status": "success",
  "objective": "balanced",
  "total_candidates_evaluated": 8,
  "feasible_candidates_count": 2,
  "recommended_candidate": {
    "candidate_id": "upgrade-db-1-tier",
    "description": "Candidate optimizing Upgraded 'db-1' vertical tier: capacity from 600.0 to 900.0 RPS",
    "modifications": [
      "Upgraded 'db-1' vertical tier: capacity from 600.0 to 900.0 RPS, cost from $150.00 to $210.00/mo"
    ],
    "is_feasible": true,
    "rank": 1
  },
  "trade_off_analysis": "Evaluated 8 candidate architectures; 2 met all hard constraints.\nRecommended Candidate: 'upgrade-db-1-tier' under objective 'balanced'.\n- Modifications: Upgraded 'db-1' vertical tier: capacity from 600.0 to 900.0 RPS, cost from $150.00 to $210.00/mo\n- p95 Latency: 1344.27 ms -> 69.07 ms (-94.9%)\n- Throughput: 615.6 RPS -> 754.5 RPS (+22.6%)\n- Monthly Cost: $315.00 -> $375.00 (+60.00 USD)\n- Error Rate: 18.41% -> 0.00%\nTrade-off: Invested $60.00/mo to reduce p95 latency by 94.9%."
}
```

---

### 3.3 `POST /api/chaos/run`

Evaluates system resilience by injecting isolated fault scenarios and comparing baseline vs. degraded behavior.

#### Request Example

```json
{
  "architecture": { ... },
  "workload": {
    "requests_per_second": 500.0,
    "duration_seconds": 30.0,
    "seed": 42
  },
  "scenario": {
    "name": "Database Slowdown Spike",
    "failure_type": "db_slowdown",
    "target_component_id": "db-1",
    "start_time_sec": 5.0,
    "duration_sec": 15.0,
    "degradation_factor": 3.0,
    "recovery_mode": "instant_recovery"
  }
}
```

Supported `failure_type` values:
- `"api_crash"`: Target server crashes; surviving replicas absorb load if redundant, else drops requests.
- `"replica_loss"`: Decreases active replica count by `degradation_factor`.
- `"db_slowdown"`: Increases database base latency by `degradation_factor`.
- `"db_outage"`: Total database outage; drops DB writes and cache-miss reads.
- `"cache_outage"`: Cache stops serving hits (100% cache misses); floods downstream DB.
- `"timeout"`: Simulates dependency timeout failure.
- `"traffic_spike"`: Surges global traffic rate by `degradation_factor`.

---

## 4. In-Process Python Service Facade

If Member 1 prefers direct Python function calls over HTTP:

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
    max_candidates=8,
)

# 3. Chaos Simulation
chaos_result = simulate_failure(
    architecture=architecture_dict,
    workload=workload_dict,
    scenario=scenario_dict,
)
```

---

## 5. Running the API Locally

```powershell
# Run using uvicorn (with test app or main application)
python -c "import uvicorn, fastapi; from backend.api.routes import router; app = fastapi.FastAPI(); app.include_router(router); uvicorn.run(app, host='127.0.0.1', port=8000)"
```

Visit `http://127.0.0.1:8000/docs` to test endpoints interactively via Swagger UI.

---

## 6. Running Automated Tests

```powershell
python -m pytest backend/tests -v
```

All 58 unit, integration, and API tests run locally without cloud dependencies.
