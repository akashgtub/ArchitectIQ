# ArchitectIQ — API Reference Specification

ArchitectIQ exposes a comprehensive RESTful API built on FastAPI. Interactive Swagger OpenAPI documentation is accessible at `http://localhost:8000/docs` and Redoc at `http://localhost:8000/redoc`.

---

## 1. System Health & Observability Endpoints

### `GET /health`
Validates backend system availability.
- **Request**: `GET /health`
- **Response**: HTTP 200 OK
```json
{
  "status": "healthy"
}
```

### `GET /api/v1/health`
Detailed service metadata and timestamp.
- **Request**: `GET /api/v1/health`
- **Response**: HTTP 200 OK
```json
{
  "status": "healthy",
  "service": "ArchitectIQ - System Architecture Analysis & Simulation Agent",
  "timestamp": "2026-11-08T14:50:46.165656+00:00",
  "schema_version": "1.0"
}
```

### `GET /metrics`
Prometheus metric exposition endpoint scraped by Prometheus server.
- **Response**: Plain text format containing metric counters, gauges, and histograms (`architectiq_http_requests_total`, `architectiq_http_request_duration_seconds`).

---

## 2. Core Architecture Simulation & Optimization Endpoints

### `POST /api/simulation/run`
Executes discrete-event queue simulation against a user-defined architecture topology and workload.
- **Request Body**:
```json
{
  "architecture": {
    "components": [
      {
        "id": "lb-1",
        "type": "load_balancer",
        "name": "Public Ingress Load Balancer",
        "capacity_rps": 2500.0,
        "replicas": 1,
        "base_latency_ms": 1.5,
        "cost_per_month_usd": 25.0
      },
      {
        "id": "api-1",
        "type": "api_server",
        "name": "App API Gateway Server",
        "capacity_rps": 500.0,
        "replicas": 2,
        "base_latency_ms": 10.0,
        "cost_per_month_usd": 40.0
      },
      {
        "id": "cache-1",
        "type": "cache",
        "name": "Redis Distributed In-Memory Cache",
        "capacity_rps": 3000.0,
        "replicas": 1,
        "base_latency_ms": 2.0,
        "cache_hit_ratio": 0.85,
        "cost_per_month_usd": 60.0
      },
      {
        "id": "db-1",
        "type": "database",
        "name": "Primary PostgreSQL Database",
        "capacity_rps": 800.0,
        "replicas": 1,
        "base_latency_ms": 25.0,
        "cost_per_month_usd": 150.0
      }
    ],
    "connections": [
      { "source": "lb-1", "target": "api-1", "protocol": "http", "latency_overhead_ms": 1.0, "path_type": "both" },
      { "source": "api-1", "target": "cache-1", "protocol": "redis", "latency_overhead_ms": 0.5, "path_type": "read" },
      { "source": "api-1", "target": "db-1", "protocol": "sql", "latency_overhead_ms": 1.5, "path_type": "write" },
      { "source": "cache-1", "target": "db-1", "protocol": "sql", "latency_overhead_ms": 1.0, "path_type": "read" }
    ]
  },
  "workload": {
    "requests_per_second": 600.0,
    "read_ratio": 0.85,
    "duration_seconds": 10.0,
    "pattern": "constant"
  },
  "constraints": {
    "max_p95_latency_ms": 150.0,
    "monthly_budget_usd": 500.0,
    "min_throughput_rps": 550.0,
    "max_error_rate": 0.05
  }
}
```
- **Response**: HTTP 200 OK
```json
{
  "simulation_type": "baseline",
  "status": "success",
  "metrics": {
    "throughput_rps": 612.6,
    "p50_latency_ms": 15.76,
    "p95_latency_ms": 28.45,
    "p99_latency_ms": 42.10,
    "error_rate": 0.0,
    "total_monthly_cost_usd": 315.0
  },
  "bottlenecks": []
}
```

---

### `POST /api/optimization/run`
Applies multi-objective Pareto optimization (NSGA-II) to synthesize alternative architectures balancing cost, throughput, and p95 latency.
- **Request Body**: Same architecture and constraints payload as `/api/simulation/run`.
- **Response**: HTTP 200 OK
```json
{
  "status": "success",
  "pareto_frontier": [ ... ],
  "recommendation": {
    "name": "Cost-Optimized Scale Candidate",
    "cost_savings_pct": 28.5,
    "latency_impact_pct": 3.2
  }
}
```

---

### `POST /api/chaos/run`
Injects simulated faults (e.g. latency spikes, node crashes, packet drop) to evaluate architecture resilience.
- **Response**: HTTP 200 OK containing comparative baseline vs fault performance and resilience degradation score.

