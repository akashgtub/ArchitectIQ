# ArchPilot AI — The Self-Testing System Design Agent

## Member 1: Architecture Understanding & Root-Cause Investigation

ArchPilot AI is an autonomous, self-testing system design and optimization agent.
**Member 1** implements the continuous AI architecture ingestion and diagnostic investigation pipeline:

1. **Image Ingestion & Validation**: Safe inspection of architecture diagrams with Pillow (format verification, dimension limits, byte limits, integrity checks).
2. **Gemma / Gemini Model Extraction**: Extracts structured component topologies, visible attributes, workloads, constraints, and distinguishes directly observed facts from inferences and unknown variables.
3. **Graph & Workload Validation**: Uses NetworkX and Pydantic to validate endpoints, detect duplicate IDs, check workload consistency (RPS, read/write ratios), and surface ambiguities without hallucinating.
4. **Member 2 Simulator Adapter**: Communicates with Member 2's baseline simulation engine (HTTP adapter) or deterministic mock simulator with explicit labeling (`is_mock=True`, `source="mock_simulator"`).
5. **Root-Cause Investigation Engine**: Formulates testable hypotheses with controlled confidence categories (`low`, `medium`, `high`), dispatches targeted diagnostic experiments from a supported allowlist within budget limits, and evaluates metric deltas.
6. **Member 2 Optimization Handoff**: Produces a strictly validated, versioned JSON handoff (`Member1Handoff`, Schema `1.0`) ready for direct ingestion by Member 2's optimizer and failure-testing engine.

---

## Architecture and Directory Layout

```text
ArchitectIQ/
├── .env.example                     # Documented configuration template
├── .gitignore                       # Git ignore rules for secrets and build artifacts
├── pytest.ini                       # Pytest configuration
├── README.md                        # Documentation and integration guide
└── backend/
    ├── __init__.py
    ├── config.py                    # Settings and budget thresholds
    ├── main.py                      # FastAPI application entrypoint
    ├── ai_agent/
    │   ├── __init__.py
    │   ├── image_validator.py       # Pillow-based image security and format checks
    │   ├── gemma_client.py          # Google Gemini / Gemma structured extraction client
    │   ├── graph_validator.py       # NetworkX graph topology and workload validator
    │   ├── architecture_parser.py   # Orchestration service for parsing and validation
    │   ├── root_cause.py            # Evidence-based hypothesis generation and diagnostic ledger
    │   └── handoff_builder.py       # Member 2 Optimization Handoff assembler
    ├── shared/
    │   ├── __init__.py
    │   └── schemas.py               # Shared canonical Pydantic data contract (v1.0)
    ├── integrations/
    │   ├── __init__.py
    │   └── simulator_client.py      # Member 2 simulator adapter & deterministic mock
    ├── api/
    │   ├── __init__.py
    │   └── routes.py                # REST API endpoints (analyze, investigations, handoff)
    └── tests/
        ├── __init__.py
        ├── test_architecture_parser.py
        ├── test_graph_validator.py
        ├── test_simulator_client.py
        ├── test_root_cause.py
        ├── test_handoff_builder.py
        └── test_api.py
```

---

## Setup & Running Locally

### 1. Requirements
* Python 3.11+
* Dependencies: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `Pillow`, `networkx`, `pytest`, `pytest-asyncio`, `google-genai`

### 2. Install Dependencies
```bash
pip install -r requirements.txt # or:
pip install fastapi uvicorn pydantic httpx Pillow networkx pytest pytest-asyncio google-genai
```

### 3. Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | `""` | Google Gemini API key. If empty, runs in deterministic mock mode for local testing. |
| `GEMINI_MODEL_ID` | `gemini-2.0-flash` | Configured model ID (`gemini-2.0-flash`, `gemini-1.5-flash`, or `gemma-2-27b-it`). |
| `SIMULATOR_BASE_URL` | `http://localhost:8001` | Base URL of Member 2's simulation engine. |
| `USE_MOCK_SIMULATOR` | `true` | When true or if simulator is unreachable, uses deterministic mock simulator. |
| `MAX_DIAGNOSTIC_EXPERIMENTS` | `3` | Maximum diagnostic experiments per investigation. |
| `INVESTIGATION_TIMEOUT_SECONDS`| `60` | Safety budget wall-clock timeout. |
| `MAX_IMAGE_SIZE_BYTES` | `10485760` (10MB) | Max image upload size. |

### 4. Running the Backend Server
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive OpenAPI Swagger documentation available at:
`http://localhost:8000/docs`

### 5. Running the Automated Test Suite
```bash
pytest -v
```

---

## API Endpoints

### 1. `POST /api/v1/architecture/analyze`
* Accepts: `multipart/form-data` with `image` (PNG, JPEG, WEBP), `requirements` (text), `workload_json` (optional), `constraints_json` (optional).
* Returns: `ArchitectureAnalyzeResponse` containing parsed `Architecture`, `ArchitectureValidationResult`, direct visual observations, inferred assumptions, and clarification questions.

### 2. `POST /api/v1/investigations`
* Accepts: `StartInvestigationRequest` containing validated `Architecture` and budget limits.
* Executes:
  - Baseline simulation via simulator adapter
  - Root-cause hypothesis generation
  - Diagnostic experiments from allowlist (`increase_workload`, `vary_read_write_mix`, `simulate_db_latency`, `scale_component`, `toggle_cache`)
  - Member 2 handoff construction
* Returns: `InvestigationDetailResponse` with status, baseline metrics, hypotheses, and handoff ready indicator.

### 3. `GET /api/v1/investigations/{investigation_id}`
* Returns investigation status, baseline metrics, executed experiments, and findings.

### 4. `GET /api/v1/investigations/{investigation_id}/handoff`
* Returns the complete, validated `Member1Handoff` JSON payload.

---

## Member 2 Integration Guide

Member 2's optimization engine can directly fetch the validated handoff JSON:
```python
import httpx
from backend.shared.schemas import Member1Handoff

response = httpx.get("http://localhost:8000/api/v1/investigations/{investigation_id}/handoff")
handoff = Member1Handoff.model_validate(response.json())

# Member 2 accesses:
# 1. Original architecture and workload: handoff.architecture
# 2. Hard constraints to preserve: handoff.optimization_handoff.hard_constraints
# 3. Confirmed bottlenecks to optimize: handoff.optimization_handoff.confirmed_findings
# 4. Target components: handoff.optimization_handoff.recommended_targets
# 5. Required comparison metrics: handoff.optimization_handoff.required_comparison_metrics
```

When Member 2 deploys their real simulation engine, set:
```bash
SIMULATOR_BASE_URL=http://<member-2-host>:<port>
USE_MOCK_SIMULATOR=false
```
The simulator client will automatically dispatch baseline requests to `POST {SIMULATOR_BASE_URL}/api/v1/simulate/baseline` and diagnostic requests to `POST {SIMULATOR_BASE_URL}/api/v1/simulate/diagnostic`.
