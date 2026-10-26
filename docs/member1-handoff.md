# Member 1 Handoff Documentation for Member 2

**Author:** Member 1 (Architecture Understanding & Root-Cause Investigation)
**Target:** Member 2 (Architecture Optimization, Simulation & Failure Testing)
**Branch:** `member1-architecture-analysis`
**Shared Schema Version:** `1.0`

---

## 1. Branch and Repository Details

* **Repository:** `origin https://github.com/akashgtub/ArchitectIQ`
* **Feature Branch:** `member1-architecture-analysis`
* **Upstream Tracking:** `origin/member1-architecture-analysis`
* **Initial Commit:** `a680b95` (feat: implement Member 1 architecture analysis and root-cause modules)

---

## 2. Modules Included

The Member 1 implementation includes the following production-tested components:

1. **AI Model Client (`backend/ai_agent/gemma_client.py`):**
   * Google Gemini / Gemma structured output extractor.
   * Categorizes information into: directly observed visual elements, inferred assumptions, and unknown parameters.
   * Bounded retries and transparent mock fallback when API keys are not configured.
2. **Image Ingestion & Validation (`backend/ai_agent/image_validator.py`):**
   * Pillow-based validation enforcing format (`PNG`, `JPEG`, `WEBP`), dimension limits (10px to 4096px), and byte size bounds (10MB).
   * Rejects corrupt uploads with structured error codes.
3. **Graph & Workload Validator (`backend/ai_agent/graph_validator.py`):**
   * NetworkX-powered directed graph validation.
   * Enforces component ID uniqueness, valid endpoints, non-negative workload values, and ratio consistency ($R + W = 1.0$).
   * Flags isolated nodes and cyclical paths with warnings rather than fatal crashes.
4. **Architecture Parser Service (`backend/ai_agent/architecture_parser.py`):**
   * Coordinates image inspection, model extraction, and graph validation into a single pipeline.
5. **Root-Cause Investigation Engine (`backend/ai_agent/root_cause.py`):**
   * Formulates bottleneck hypotheses with controlled confidence categories (`low`, `medium`, `high`).
   * Selects diagnostic experiments from a supported allowlist.
   * Computes metric differences against baseline measurements and updates verification status (`candidate`, `supported`, `confirmed`, `rejected`, `insufficient_evidence`).
   * Enforces safety budget limits (`max_diagnostic_experiments=3`, `timeout_seconds=60`).
6. **Member 2 Optimization Handoff Builder (`backend/ai_agent/handoff_builder.py`):**
   * Builds the definitive `Member1Handoff` payload conforming to schema version `1.0`.
   * Preserves original workloads and hard constraints.
7. **Simulator Client Adapter (`backend/integrations/simulator_client.py`):**
   * HTTP client sending `mode="json"` payloads to Member 2's simulator endpoints (`/api/v1/simulate/baseline` and `/api/v1/simulate/diagnostic`).
   * Features a deterministic mock simulator for offline development, strictly labeled with `is_mock=True` and `source="mock_simulator"`.
8. **REST API Interface (`backend/api/routes.py` and `backend/main.py`):**
   * `POST /api/v1/architecture/analyze`: Diagram ingestion and extraction.
   * `POST /api/v1/investigations`: End-to-end baseline simulation and diagnostic investigation.
   * `GET /api/v1/investigations/{id}`: Status and findings retrieval.
   * `GET /api/v1/investigations/{id}/handoff`: Validated Member 2 handoff JSON.
   * `GET /health` & `GET /api/v1/health`: System health and schema version.

---

## 3. Test Suite Commands and Actual Results

All 29 automated tests pass with 100% success rate:
```bash
pytest -v
```

**Actual Results:**
```text
============================= 29 passed in 16.89s =============================
backend/tests/test_api.py (3 tests passed)
backend/tests/test_architecture_parser.py (6 tests passed)
backend/tests/test_graph_validator.py (5 tests passed)
backend/tests/test_handoff_builder.py (3 tests passed)
backend/tests/test_root_cause.py (5 tests passed)
backend/tests/test_simulator_client.py (7 tests passed)
```

---

## 4. Simulator Integration Status (Mock vs. Real)

* **Current Default:** Deterministic mock adapter (`USE_MOCK_SIMULATOR=true`) for standalone execution without depending on external services.
* **Real Simulator Support:** Built-in. When Member 2 launches their engine, set `SIMULATOR_BASE_URL=http://<host>:<port>` and `USE_MOCK_SIMULATOR=false`. The client will dispatch real HTTP requests and mark responses with `is_mock: false` and `source: "member2_simulator"`.

---

## 5. Expected Architecture and Handoff JSON Format

Member 2 can deserialize the handoff directly using `Member1Handoff`:
```python
import httpx
from backend.shared.schemas import Member1Handoff

response = httpx.get("http://localhost:8000/api/v1/investigations/{id}/handoff")
handoff = Member1Handoff.model_validate(response.json())

# Member 2 extracts:
arch = handoff.architecture
hard_constraints = handoff.optimization_handoff.hard_constraints
target_components = handoff.optimization_handoff.recommended_targets
baseline_metrics = handoff.baseline.metrics
```

### Key Contract Guarantees
* Schema version: `"1.0"`.
* Workload and constraints are guaranteed to match the user's validated baseline specification.
* Confirmed findings include traceable evidence references (`run_id`, `metric_name`, `observed_value`, `diff`, `unit`).
* No unmeasured metrics are fabricated.

---

## 6. Integration Tasks for Member 2

1. **Expose Simulation Endpoints:**
   * `POST /api/v1/simulate/baseline`
   * `POST /api/v1/simulate/diagnostic`
2. **Support Allowlisted Diagnostic Experiments:**
   * `increase_workload`
   * `vary_read_write_mix`
   * `simulate_db_latency`
   * `scale_component`
   * `toggle_cache`
   * `isolate_dependency`
3. **Preserve Baseline Conditions in Optimization:**
   * Run optimization candidates under identical `requests_per_second`, `read_ratio`, and `write_ratio`.
   * Enforce all entries in `handoff.optimization_handoff.hard_constraints`.

---

## 7. Environment Variables (Names Only)

* `GEMINI_API_KEY`: API key for Gemini / Gemma multimodal extraction (optional for local mock testing).
* `GEMINI_MODEL_ID`: Default `gemini-2.0-flash`.
* `SIMULATOR_BASE_URL`: Base URL of Member 2 simulator (e.g., `http://localhost:8001`).
* `USE_MOCK_SIMULATOR`: `true` or `false`.
* `SIMULATOR_TIMEOUT_SECONDS`: Request timeout limit.
* `MAX_DIAGNOSTIC_EXPERIMENTS`: Maximum experiment budget (default `3`).
* `INVESTIGATION_TIMEOUT_SECONDS`: Total investigation timeout budget.
* `ENVIRONMENT`: `development` or `production`.
* `CORS_ORIGINS`: Allowed origins list.

---

## 8. Exact Git Commands for Member 2

### If Member 2 does not have the repo locally:
```bash
git clone https://github.com/akashgtub/ArchitectIQ.git
cd ArchitectIQ
git switch --track origin/member1-architecture-analysis
```

### If Member 2 already has the repo locally:
```bash
git fetch origin
git switch --track origin/member1-architecture-analysis
```

### If Member 2 is working on their own branch (`feature/simulation-engine`) and wants to integrate:
```bash
git fetch origin
# Option A: Merge Member 1's branch
git merge origin/member1-architecture-analysis

# Option B: Rebase onto Member 1's branch
git rebase origin/member1-architecture-analysis
```
