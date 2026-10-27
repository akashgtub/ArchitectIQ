# ArchitectIQ — Autonomous AI Agent for System Architecture Analysis, Optimization, and Resilience Testing

ArchitectIQ is an end-to-end autonomous AI system engineering platform. It ingests system architecture diagrams, validates graph topologies, executes workload-driven discrete-event simulations, discovers performance bottlenecks via AI root-cause analysis, synthesizes alternative candidate architectures through deterministic multi-objective optimization, and stresses systems using chaos engineering resilience experiments.

---

## 🏛️ System Architecture & Integrated Modules

ArchitectIQ brings together two key module suites behind a unified FastAPI application and a modern, responsive web user interface:

### 1. Architecture Understanding & Root-Cause Investigation (Member 1)
* **Image Diagram Ingestion & Security**: Pillow-based format verification (`PNG`, `JPEG`, `WEBP`), dimension bounds (10px–4096px), byte bounds (10MB), and corruption detection.
* **Multimodal AI Architecture Extraction**: Google Gemini / Gemma structured extraction distinguishing visual facts, inferred components, and unknown variables.
* **Graph & Workload Validation**: NetworkX directed topology verification, endpoint matching, duplicate ID rejection, and ratio consistency ($R + W = 1.0$).
* **Root-Cause Investigation Engine**: Formulates hypotheses with controlled confidence categories (`low`, `medium`, `high`) and executes allowlisted diagnostic experiments.
* **Traceable Optimization Handoff**: Assembles versioned `Member1Handoff` payloads conforming to Schema Version `1.0`.

### 2. Discrete Simulation, Optimization & Chaos Engineering (Member 2)
* **Discrete-Event Simulation Engine**: Workload-driven performance simulator computing latency percentiles (p50, p95, p99), queuing dynamics, throughput RPS, error rates, and component utilization.
* **Deterministic Architecture Optimizer**: Multi-objective candidate search (Balanced, Minimize Latency, Minimize Cost, Maximize Throughput) evaluating mutated candidate architectures against baseline workloads.
* **Chaos Engineering & Resilience Lab**: Fault injection simulations (Database slowdown, API crash/replica loss, cache tier outage, dependency timeout, sudden traffic spikes) measuring degradation deltas and recovery.
* **Schema Adapter & Direct Simulator Facade**: Seamless adapter (`backend/shared/adapter.py`) bridging Member 1 canonical schemas with Member 2 physics simulation models.

### 3. Integrated Web Application
* **Modern Web Interface**: Responsive single-page application built with a sleek purple-and-white theme, clean surface cards, interactive topology badges, live metric gauges, and Pareto trade-off comparisons.
* **Direct FastAPI Integration**: Automatically served directly from `http://localhost:8000/` or standalone via Vite dev server (`http://localhost:5173/`).

---

## 📁 Repository Layout

```text
ArchitectIQ/
├── .env.example                     # Environment configuration template
├── .gitignore                       # Git ignore rules for secrets, builds, node_modules
├── build.sh                         # Production build script for Render
├── render.yaml                      # Render Blueprint Infrastructure-as-Code specification
├── pytest.ini                       # Pytest configuration
├── requirements.txt                 # Python production dependencies (FastAPI, Uvicorn, NumPy, etc.)
├── README.md                        # Project documentation
├── backend/
│   ├── config.py                    # Application settings and limits
│   ├── main.py                      # FastAPI application entrypoint & static mounting
│   ├── ai_agent/                    # Member 1 AI understanding & root-cause modules
│   │   ├── image_validator.py       # Pillow security and validation
│   │   ├── gemma_client.py          # Gemini/Gemma multimodal extraction client
│   │   ├── graph_validator.py       # NetworkX topology and workload validation
│   │   ├── architecture_parser.py   # Diagram extraction orchestration service
│   │   ├── providers.py             # Unified AI provider abstraction (Gemini, HF, Gemma, Fallback)
│   │   ├── root_cause.py            # Diagnostic experiment and hypothesis ledger
│   │   └── handoff_builder.py       # Member 2 Optimization Handoff assembler
│   ├── api/                         # Unified REST API service and routes
│   │   ├── service.py               # Functional service facade for simulation & optimization
│   │   └── routes.py                # Standalone & unified FastAPI router
│   ├── simulator/                   # Member 2 Discrete simulation engine
│   │   ├── schemas.py               # Simulation Pydantic v2 data models
│   │   ├── workload.py              # Synthetic workload generation profiles
│   │   ├── performance.py           # Latency distribution and metrics calculations
│   │   └── engine.py                # Discrete-event simulation engine
│   ├── optimizer/                   # Member 2 Architecture optimizer
│   │   └── optimizer.py             # Candidate generation, ranking, and trade-off search
│   ├── chaos_lab/                   # Member 2 Chaos engineering resilience lab
│   │   └── failure_simulator.py     # Fault injection scenarios and impact analysis
│   ├── shared/                      # Shared canonical contracts and adapters
│   │   ├── schemas.py               # Canonical data contract (Schema v1.0)
│   │   └── adapter.py               # Bidirectional schema and simulator adapter
│   ├── integrations/
│   │   └── simulator_client.py      # Simulator client adapter and mock engine
│   ├── examples/
│   │   ├── sample_architecture.json # Validated sample architecture specification
│   │   ├── optimization_request.json# Sample optimization request
│   │   └── resilience_scenario.json # Sample resilience scenario
│   └── tests/                       # Complete automated test suite (122 passing tests)
└── frontend/                        # Modern responsive web application
    ├── package.json                 # Node dependencies and build scripts
    ├── package-lock.json            # Deterministic lockfile for reproducible npm ci builds
    ├── vite.config.js               # Vite dev server configuration with proxy
    ├── index.html                   # Semantic HTML5 layout
    ├── src/
    │   ├── style.css                # Design system, glassmorphism, responsive styles
    │   ├── api.js                   # Reusable API client module
    │   └── app.js                   # Interactive UI controller and workflow manager
    └── test/
        ├── api.test.js              # Frontend client unit tests
        └── lifecycle_and_integrity.test.js # Frontend state lifecycle & regression tests (13 passing tests)
```

---

## 🚀 Setup & Execution Guide

### Prerequisites
* Python 3.11+
* Node.js v18+ and npm (for frontend compilation and tests)

### Local Development

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   npm --prefix frontend install
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

3. **Start the Unified Backend Server**:
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   * **Web Dashboard**: Open [http://localhost:8000/](http://localhost:8000/)
   * **Interactive API Swagger Docs**: Open [http://localhost:8000/docs](http://localhost:8000/docs)
   * **Health Check Endpoint**: Open [http://localhost:8000/health](http://localhost:8000/health)

4. **Optional Standalone Frontend Development Server**:
   ```bash
   npm --prefix frontend run dev
   ```
   The Vite dev server proxies API and health requests to `http://localhost:8000`.

---

## 🌐 Production Deployment on Render

ArchitectIQ is architected for zero-downtime, single-service deployment on Render as a **Web Service**. FastAPI serves both the REST API and the compiled Vite frontend from one public URL without requiring external Node servers.

### Method A: Blueprint Deployment (Recommended)

1. Connect your GitHub repository to [Render](https://dashboard.render.com/).
2. Select **Blueprints** > **New Blueprint Instance**.
3. Choose the repository `akashgtub/ArchitectIQ` and branch `feature/simulation-engine`.
4. Render automatically parses `render.yaml` and configures the service:
   * **Service Name**: `architectiq`
   * **Runtime**: `Python 3.11.9`
   * **Build Command**: `bash build.sh`
   * **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   * **Health Check Path**: `/health`
5. In the Render Dashboard under **Environment**, configure your secret API keys (see Environment Variables below).
6. Click **Apply**.

### Method B: Manual Web Service Setup

If configuring manually via the Render Dashboard:

1. Click **New +** > **Web Service**.
2. Connect `https://github.com/akashgtub/ArchitectIQ` and select branch `feature/simulation-engine`.
3. Set the configuration:
   * **Environment**: `Python`
   * **Region**: Choose closest to your users (e.g. `Oregon (US West)` or `Frankfurt (EU Central)`).
   * **Branch**: `feature/simulation-engine`
   * **Build Command**: `bash build.sh`
   * **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   * **Plan**: `Starter` or `Free`
4. Under **Advanced**:
   * **Health Check Path**: `/health`
   * **Auto-Deploy**: `Yes`
5. Under **Environment Variables**, add the environment variables detailed below.

---

## 🔑 Environment Variables Reference

Configure non-secret variables in `render.yaml` and secret API keys in the Render Dashboard (**Environment** tab):

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `ENVIRONMENT` | Optional | `production` | Operational environment mode (`production`, `development`). |
| `PORT` | Auto (Render) | `8000` | Render dynamically assigns this port; Uvicorn binds automatically. |
| `AI_PROVIDER` | Optional | `auto` | Primary text AI provider: `auto`, `huggingface`, `gemini`, `gemma`, `deterministic_fallback`. |
| `ALLOW_AI_FALLBACK`| Optional | `true` | Allows transparent, deterministic fallback when live AI keys are missing or rate-limited. |
| `VISION_AI_PROVIDER`| Optional | `gemini` | Provider used for diagram image analysis. |
| `TEXT_AI_PROVIDER`| Optional | `huggingface`| Provider used for root-cause and trade-off analysis. |
| `GEMINI_API_KEY` | Optional* | None | Google Gemini API key for multimodal diagram parsing. |
| `GEMINI_MODEL_ID` | Optional | `gemini-flash-latest` | Google Gemini model identifier. |
| `HF_TOKEN` | Optional* | None | Hugging Face user access token for text reasoning. |
| `HF_MODEL` | Optional | `google/gemma-2-27b-it` | Hugging Face model repository. |
| `HF_BASE_URL` | Optional | `https://router.huggingface.co/v1` | Hugging Face router base URL. |
| `GEMMA_API_KEY` | Optional | None | Direct Google Gemma API key (falls back to `GEMINI_API_KEY`). |
| `GEMMA_MODEL_ID` | Optional | `gemma-2-27b-it` | Gemma model identifier. |
| `GEMMA_BASE_URL` | Optional | None | Custom self-hosted inference URL (e.g. vLLM, Ollama, Groq). |
| `USE_MOCK_SIMULATOR`| Optional | `false` | `false` runs the real physics-based simulation engine; `true` uses deterministic mock data. |
| `SIMULATOR_BASE_URL`| Optional | None | Optional external HTTP simulation engine URL. If empty, runs in-process engine. |
| `CORS_ORIGINS` | Optional | `*` | Allowed CORS origins for external API access. |

*\* Note: When API keys are omitted, ArchitectIQ operates in deterministic fallback mode with full provenance reporting. A missing AI credential never crashes the server or health checks.*

---

## 🧪 Testing & Validation

### Run Backend Pytest Suite
```bash
pytest
```
**Results:** **122 passed in 193s** (100% passing across health endpoints, route precedence, diagram parsing, discrete simulator, optimizer, chaos lab, and AI provider fallback).

### Run Frontend Unit & Regression Suite
```bash
npm --prefix frontend test
```
**Results:** **13 passed in 5s** (100% passing across API client, relative URL routing, workflow stage gatekeepers, image validation, and UI state invalidation).

### Run Production Build Locally
```bash
bash build.sh
```
Compiles the frontend with Vite into `frontend/dist/` and verifies required assets.

### Verify Deployment Endpoints
Once deployed, verify your service with:
```bash
# 1. Health Check
curl -f https://<your-render-app>.onrender.com/health

# 2. Swagger Documentation
curl -f https://<your-render-app>.onrender.com/docs

# 3. Frontend Dashboard
curl -f https://<your-render-app>.onrender.com/
```

---

## ⚠️ Known Limitations & Fallback Behavior

1. **In-Memory State Lifecycle**:
   * Investigation records (`_INVESTIGATIONS_DB`) and baseline simulation results (`_BASELINE_STORE`) are held in fast in-memory structures.
   * When Render restarts or scales instances, in-memory state is refreshed. Re-running a baseline simulation or investigation re-populates the cache immediately.
2. **AI Provider Graceful Degradation**:
   * If `GEMINI_API_KEY` or `HF_TOKEN` are not provided, or if remote APIs experience timeouts or quota limits (429), ArchitectIQ automatically falls back to `DeterministicFallbackProvider` when `ALLOW_AI_FALLBACK=true`.
   * Provenance is transparently stamped in every response (`fallback_used: true`, `model_name: "deterministic-rule-based-v1"`), ensuring no fabricated AI results are passed off as live model outputs.
3. **No Localhost Dependency**:
   * In production, the frontend uses same-origin relative URLs (`/api/...`, `/health`), completely eliminating any dependency on local machine ports or separate development servers.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Production health check (HTTP 200 without external AI dependencies) |
| `GET` | `/api/v1/health` | Versioned system health check |
| `GET` | `/` | Web application dashboard |
| `GET` | `/docs` | OpenAPI / Swagger interactive documentation |
| `POST` | `/api/simulation/run` | Run baseline discrete-event performance simulation |
| `POST` | `/api/optimization/run` | Run candidate generation and multi-objective optimization |
| `POST` | `/api/chaos/run` | Run fault injection chaos resilience testing |
| `POST` | `/api/v1/architecture/analyze` | Ingest diagram image and extract architecture components |
| `POST` | `/api/v1/investigations` | Run baseline simulation and root-cause analysis |
| `GET` | `/api/v1/investigations/{id}` | Retrieve investigation findings and hypothesis status |
| `GET` | `/api/v1/investigations/{id}/handoff`| Retrieve validated optimization handoff JSON |
| `POST` | `/api/v1/simulate/baseline` | Member 2 discrete engine baseline simulation adapter |
| `POST` | `/api/v1/simulate/diagnostic` | Member 2 discrete engine diagnostic experiment adapter |

