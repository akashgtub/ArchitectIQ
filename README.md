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
├── pytest.ini                       # Pytest configuration
├── requirements.txt                 # Python dependencies
├── README.md                        # Project documentation
├── backend/
│   ├── config.py                    # Application settings and limits
│   ├── main.py                      # FastAPI application entrypoint & static mounting
│   ├── ai_agent/                    # Member 1 AI understanding & root-cause modules
│   │   ├── image_validator.py       # Pillow security and validation
│   │   ├── gemma_client.py          # Gemini/Gemma multimodal extraction client
│   │   ├── graph_validator.py       # NetworkX topology and workload validation
│   │   ├── architecture_parser.py   # Diagram extraction orchestration service
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
│   └── tests/                       # Complete automated test suite (88 passing tests)
└── frontend/                        # Modern responsive web application
    ├── package.json                 # Node dependencies and build scripts
    ├── vite.config.js               # Vite dev server configuration with proxy
    ├── index.html                   # Semantic HTML5 layout
    ├── src/
    │   ├── style.css                # Design system, glassmorphism, responsive styles
    │   ├── api.js                   # Reusable API client module
    │   └── app.js                   # Interactive UI controller and workflow manager
    └── test/
        └── api.test.js              # Frontend client unit tests
```

---

## 🚀 Setup & Execution Guide

### Prerequisites
* Python 3.11+
* Node.js v18+ and npm (for frontend build/tests)

### 1. Install Backend Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Key configuration parameters:
* `GEMINI_API_KEY`: Google Gemini API key. If left blank, the system automatically uses deterministic mock analysis for zero-cost offline development.
* `GEMINI_MODEL_ID`: Default `gemini-2.0-flash`.
* `USE_MOCK_SIMULATOR`: When `false`, root-cause investigations invoke Member 2's real simulation engine via the integrated adapter.

### 3. Install Frontend Dependencies (Optional for Vite dev)
```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Start the Application
Start the unified FastAPI server:
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
* **Web User Interface**: Open [http://localhost:8000/](http://localhost:8000/) in any modern browser.
* **Interactive API Swagger Docs**: Open [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 🧪 Testing and Validation

### Run Backend Test Suite
```bash
python -m pytest backend/tests -v
```
**Results:** **88 passed** (100% success rate across all schema, simulator, optimizer, failure simulator, graph validator, root cause, and API integration tests).

### Run Frontend Test Suite & Production Build
```bash
cd frontend
npm test
npm run build
```
**Results:** **2 passed**, production bundle built cleanly in `frontend/dist/`.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | System health check and schema version |
| `POST` | `/api/simulation/run` | Run baseline discrete-event performance simulation |
| `POST` | `/api/optimization/run` | Run candidate generation and multi-objective optimization |
| `POST` | `/api/chaos/run` | Run fault injection chaos resilience testing |
| `POST` | `/api/v1/architecture/analyze` | Ingest diagram image and extract architecture components |
| `POST` | `/api/v1/investigations` | Run baseline simulation and root-cause analysis |
| `GET` | `/api/v1/investigations/{id}` | Retrieve investigation findings and hypothesis status |
| `GET` | `/api/v1/investigations/{id}/handoff`| Retrieve validated optimization handoff JSON |
| `POST` | `/api/v1/simulate/baseline` | Member 2 discrete engine baseline simulation adapter |
| `POST` | `/api/v1/simulate/diagnostic` | Member 2 discrete engine diagnostic experiment adapter |
