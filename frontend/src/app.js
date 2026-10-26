/**
 * ArchitectIQ - Autonomous AI Agent Frontend Application Controller
 * Wires the interactive UI to the FastAPI backend endpoints with strict
 * lifecycle management, workflow dependency enforcement, and real data integrity.
 */

import { api } from './api.js';

// Predefined Real-World Architecture Presets (Explicitly labelled demonstration samples)
const PRESET_ARCHITECTURES = {
  ecommerce: {
    name: "E-Commerce Microservices Platform",
    architecture_id: "arch-ecommerce-01",
    components: [
      { id: "lb-1", type: "load_balancer", name: "Public Ingress LB", capacity_rps: 5000, replicas: 2, base_latency_ms: 2.0, cost_per_month_usd: 50.0 },
      { id: "api-gateway", type: "api_server", name: "Storefront Gateway", capacity_rps: 1200, replicas: 3, base_latency_ms: 12.0, cost_per_month_usd: 120.0 },
      { id: "cache-redis", type: "cache", name: "Product Catalog Cache", capacity_rps: 8000, replicas: 1, base_latency_ms: 1.5, cost_per_month_usd: 60.0, cache_hit_ratio: 0.85 },
      { id: "db-primary", type: "database", name: "PostgreSQL Primary", capacity_rps: 800, replicas: 1, base_latency_ms: 25.0, cost_per_month_usd: 140.0 },
      { id: "queue-orders", type: "message_broker", name: "RabbitMQ Orders", capacity_rps: 4000, replicas: 1, base_latency_ms: 4.0, cost_per_month_usd: 35.0 },
      { id: "worker-billing", type: "api_server", name: "Billing Consumer", capacity_rps: 600, replicas: 2, base_latency_ms: 30.0, cost_per_month_usd: 80.0 }
    ],
    connections: [
      { source: "lb-1", target: "api-gateway", protocol: "http", latency_overhead_ms: 1.0 },
      { source: "api-gateway", target: "cache-redis", protocol: "redis", latency_overhead_ms: 1.2 },
      { source: "api-gateway", target: "db-primary", protocol: "sql", latency_overhead_ms: 2.0 },
      { source: "api-gateway", target: "queue-orders", protocol: "amqp", latency_overhead_ms: 1.5 },
      { source: "queue-orders", target: "worker-billing", protocol: "amqp", latency_overhead_ms: 1.5 }
    ],
    workload: {
      requests_per_second: 1500,
      read_ratio: 0.85,
      write_ratio: 0.15,
      duration_seconds: 10,
      burst_multiplier: 2.0
    },
    constraints: {
      max_p95_latency_ms: 180,
      min_throughput_rps: 1400,
      max_cost_per_hour: 1.50
    }
  },
  payments: {
    name: "FinTech High-Assurance Payments Gateway",
    architecture_id: "arch-payments-02",
    components: [
      { id: "waf-gateway", type: "load_balancer", name: "Cloudflare / WAF Gateway", capacity_rps: 4000, replicas: 2, base_latency_ms: 3.0, cost_per_month_usd: 60.0 },
      { id: "payment-api", type: "api_server", name: "Card Authorization Service", capacity_rps: 1000, replicas: 2, base_latency_ms: 18.0, cost_per_month_usd: 100.0 },
      { id: "ledger-db", type: "database", name: "Aurora PostgreSQL Ledger", capacity_rps: 600, replicas: 1, base_latency_ms: 35.0, cost_per_month_usd: 220.0 }
    ],
    connections: [
      { source: "waf-gateway", target: "payment-api", protocol: "http", latency_overhead_ms: 1.5 },
      { source: "payment-api", target: "ledger-db", protocol: "sql", latency_overhead_ms: 2.5 }
    ],
    workload: {
      requests_per_second: 800,
      read_ratio: 0.3,
      write_ratio: 0.7,
      duration_seconds: 10,
      burst_multiplier: 1.5
    },
    constraints: {
      max_p95_latency_ms: 120,
      min_throughput_rps: 750,
      max_cost_per_hour: 2.00
    }
  }
};

// Component Type Mapping and Normalization for Member 1 <-> Member 2 consistency
const TYPE_MAP = {
  gateway: 'load_balancer',
  web_server: 'api_server',
  microservice: 'api_server',
  worker: 'api_server',
  cdn: 'cache',
  message_queue: 'queue',
  object_storage: 'storage',
  external_service: 'third_party_service',
  unknown: 'api_server',
};

function normalizeArchitectureForSimulation(arch) {
  if (!arch || !arch.components) return arch;
  const uniqueCompIds = new Set();
  const components = [];

  for (const c of arch.components) {
    if (!c.id || uniqueCompIds.has(c.id)) continue;
    uniqueCompIds.add(c.id);

    const normType = TYPE_MAP[c.type] || c.type || 'api_server';
    const attrs = c.attributes || {};
    const replicas = Number(c.replicas || attrs.replicas || attrs.instances || 1);

    let defaultCap = 1200;
    let defaultLat = 12.0;
    let defaultCost = 40.0;
    if (normType === 'load_balancer') { defaultCap = 5000; defaultLat = 2.0; defaultCost = 25.0; }
    else if (normType === 'cache') { defaultCap = 8000; defaultLat = 1.5; defaultCost = 60.0; }
    else if (normType === 'database') { defaultCap = 800; defaultLat = 25.0; defaultCost = 120.0; }
    else if (normType === 'queue' || normType === 'message_broker') { defaultCap = 4000; defaultLat = 4.0; defaultCost = 35.0; }

    const capacity_rps = Number(c.capacity_rps || attrs.capacity_rps || defaultCap);
    const base_latency_ms = Number(c.base_latency_ms || attrs.base_latency_ms || defaultLat);
    const cost_per_month_usd = Number(c.cost_per_month_usd || attrs.cost_per_month_usd || (defaultCost * replicas));
    const cache_hit_ratio = (normType === 'cache')
      ? Number(c.cache_hit_ratio !== undefined && c.cache_hit_ratio !== null ? c.cache_hit_ratio : (attrs.cache_hit_ratio !== undefined ? attrs.cache_hit_ratio : 0.8))
      : null;

    components.push({
      id: c.id,
      type: normType,
      name: c.name || c.id,
      capacity_rps,
      replicas,
      base_latency_ms,
      cost_per_month_usd,
      cache_hit_ratio,
    });
  }

  // Deduplicate connections and verify valid endpoints
  const seenConns = new Set();
  const connections = [];
  for (const conn of (arch.connections || [])) {
    if (!conn.source || !conn.target || !uniqueCompIds.has(conn.source) || !uniqueCompIds.has(conn.target) || conn.source === conn.target) {
      continue;
    }
    const key = `${conn.source}->${conn.target}`;
    if (seenConns.has(key)) continue;
    seenConns.add(key);

    const attrs = conn.attributes || {};
    connections.push({
      source: conn.source,
      target: conn.target,
      protocol: conn.protocol || attrs.protocol || 'http',
      latency_overhead_ms: Number(conn.latency_overhead_ms || attrs.latency_overhead_ms || 1.0),
      path_type: conn.path_type || 'both',
    });
  }

  return {
    ...arch,
    components,
    connections,
  };
}

// ============================================================================
// Global Application State (Lifecycle: EMPTY -> FILE_SELECTED -> ANALYZING -> READY / ERROR)
// ============================================================================

const state = {
  lifecycleState: 'EMPTY',        // 'EMPTY' | 'FILE_SELECTED' | 'ANALYZING' | 'READY' | 'ERROR'
  currentArchitecture: null,      // Source of truth. Null until verified parse or explicit preset load
  architectureSource: null,       // 'upload' | 'sample_preset' | null
  architectureName: null,         // Display name
  analysisProvenance: null,       // { provider, model_id, is_mock, fallback_used }
  baselineResult: null,           // Baseline simulation result (null until successful execution)
  currentInvestigation: null,     // Root-cause investigation result (null until successful run)
  optimizationResult: null,       // Optimization search result (null until successful run)
  chaosResult: null,              // Chaos experiment result (null until successful run)
  selectedFile: null,             // Selected image file object
};

// ============================================================================
// Initialization & Navigation
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initPresetSelector();
  initUploadDropzone();
  initActionButtons();
  checkBackendHealth();
  updateWorkflowAvailability();
});

function initTabs() {
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetId = tab.dataset.tab;
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const panel = document.getElementById(targetId);
      if (panel) panel.classList.add('active');
    });
  });
}

async function checkBackendHealth() {
  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');
  try {
    const health = await api.checkHealth();
    if (statusDot && statusText) {
      statusDot.style.background = '#16A34A';
      statusText.textContent = `Connected (v${health.schema_version || '1.0'})`;
    }
  } catch (err) {
    if (statusDot && statusText) {
      statusDot.style.background = '#DC2626';
      statusText.textContent = 'Backend Offline';
    }
    showAlert('global-alert', `Backend service connection warning: ${err.message}. Ensure FastAPI is running on port 8000.`, 'warning');
  }
}

// ============================================================================
// Workflow Invalidation & State Gatekeeper
// ============================================================================

/**
 * Invalidates all dependent results when architecture changes or is cleared.
 * Enforces that no stale, fabricated, or preset metrics linger after state changes.
 */
function invalidateArchitectureResults(notice = '') {
  state.baselineResult = null;
  state.currentInvestigation = null;
  state.optimizationResult = null;
  state.chaosResult = null;

  renderSimulationResults(null);
  renderInvestigationResults(null);
  renderOptimizationResults(null);
  renderChaosResults(null);

  hideAlert('simulation-alert');
  hideAlert('investigation-alert');
  hideAlert('optimization-alert');
  hideAlert('chaos-alert');

  if (notice) {
    showAlert('global-alert', notice, 'info');
  }
}

/**
 * Central gatekeeper that enables/disables UI actions and displays clear
 * dependency guidance across all 6 dashboard stages based on actual state.
 */
function updateWorkflowAvailability() {
  const hasArchitecture = Boolean(state.currentArchitecture && state.currentArchitecture.components?.length > 0);
  const hasBaseline = Boolean(state.baselineResult && state.baselineResult.metrics);

  // 1. Header Architecture Status Badge
  const archBadge = document.getElementById('header-arch-badge');
  if (archBadge) {
    if (state.lifecycleState === 'EMPTY') {
      archBadge.textContent = 'No Architecture Loaded';
      archBadge.style.background = 'var(--bg-lavender)';
      archBadge.style.color = 'var(--text-secondary)';
    } else if (state.lifecycleState === 'FILE_SELECTED') {
      archBadge.textContent = 'Diagram Selected (Unanalyzed)';
      archBadge.style.background = '#FEF3C7';
      archBadge.style.color = '#B45309';
    } else if (state.lifecycleState === 'ANALYZING') {
      archBadge.textContent = 'Analyzing Architecture...';
      archBadge.style.background = '#EDE9FE';
      archBadge.style.color = 'var(--color-primary)';
    } else if (state.lifecycleState === 'READY') {
      const label = state.architectureSource === 'sample_preset' ? `Sample Preset: ${state.architectureName}` : `Uploaded: ${state.architectureName}`;
      archBadge.textContent = label;
      archBadge.style.background = '#DCFCE7';
      archBadge.style.color = '#15803D';
    } else if (state.lifecycleState === 'ERROR') {
      archBadge.textContent = 'Architecture Error';
      archBadge.style.background = '#FEE2E2';
      archBadge.style.color = 'var(--color-error)';
    }
  }

  // 2. Stage 2: Topology Visualizer
  renderTopology();

  // 3. Stage 3: Baseline Simulation Button & Guidance
  const btnSimulate = document.getElementById('btn-simulate');
  const simDepAlert = document.getElementById('simulation-dependency-alert');
  if (btnSimulate) {
    btnSimulate.disabled = !hasArchitecture;
    if (!hasArchitecture) {
      btnSimulate.title = 'Requires an analyzed architecture from Stage 1';
      if (simDepAlert) {
        simDepAlert.className = 'alert alert-info';
        simDepAlert.innerHTML = '<strong>Stage Dependency:</strong> Baseline simulation requires an analyzed architecture. Ingest an architecture diagram or select a sample preset in Stage 1 first.';
        simDepAlert.style.display = 'block';
      }
    } else {
      btnSimulate.title = 'Execute discrete-event baseline performance simulation';
      if (simDepAlert) simDepAlert.style.display = 'none';
    }
  }

  // 4. Stage 4: Root-Cause Investigation Button & Guidance
  const btnInvestigate = document.getElementById('btn-investigate');
  const invDepAlert = document.getElementById('investigation-dependency-alert');
  if (btnInvestigate) {
    btnInvestigate.disabled = !hasArchitecture || !hasBaseline;
    if (!hasArchitecture) {
      btnInvestigate.title = 'Requires an analyzed architecture from Stage 1';
      if (invDepAlert) {
        invDepAlert.className = 'alert alert-info';
        invDepAlert.innerHTML = '<strong>Stage Dependency:</strong> Root-cause investigation requires an active architecture from Stage 1 and baseline simulation evidence from Stage 3.';
        invDepAlert.style.display = 'block';
      }
    } else if (!hasBaseline) {
      btnInvestigate.title = 'Requires baseline simulation evidence from Stage 3';
      if (invDepAlert) {
        invDepAlert.className = 'alert alert-warning';
        invDepAlert.innerHTML = '<strong>Evidence Required:</strong> Root-cause investigation requires measured baseline simulation evidence. Run Stage 3 (Baseline Simulation) before diagnosing bottlenecks.';
        invDepAlert.style.display = 'block';
      }
    } else {
      btnInvestigate.title = 'Start automated bottleneck diagnosis and diagnostic experiments';
      if (invDepAlert) invDepAlert.style.display = 'none';
    }
  }

  // 5. Stage 5: Architecture Optimizer Button & Guidance
  const btnOptimize = document.getElementById('btn-optimize');
  const optDepAlert = document.getElementById('optimization-dependency-alert');
  if (btnOptimize) {
    btnOptimize.disabled = !hasArchitecture;
    if (!hasArchitecture) {
      btnOptimize.title = 'Requires an analyzed architecture from Stage 1';
      if (optDepAlert) {
        optDepAlert.className = 'alert alert-info';
        optDepAlert.innerHTML = '<strong>Stage Dependency:</strong> Optimization search requires an analyzed architecture to mutate and evaluate. Complete Stage 1 first.';
        optDepAlert.style.display = 'block';
      }
    } else {
      btnOptimize.title = 'Explore alternative architectures and rank by Pareto trade-off';
      if (optDepAlert) optDepAlert.style.display = 'none';
    }
  }

  // 6. Stage 6: Chaos Resilience Lab Button & Target Component Selector
  const btnChaos = document.getElementById('btn-chaos');
  const selectChaosTarget = document.getElementById('select-chaos-target');
  const chaosDepAlert = document.getElementById('chaos-dependency-alert');
  if (btnChaos) {
    btnChaos.disabled = !hasArchitecture || !hasBaseline;
    if (selectChaosTarget) selectChaosTarget.disabled = !hasArchitecture;

    if (!hasArchitecture) {
      btnChaos.title = 'Requires an analyzed architecture from Stage 1';
      if (chaosDepAlert) {
        chaosDepAlert.className = 'alert alert-info';
        chaosDepAlert.innerHTML = '<strong>Stage Dependency:</strong> Chaos resilience testing requires an active architecture and baseline simulation metrics to measure degradation deltas. Complete Stages 1 & 3 first.';
        chaosDepAlert.style.display = 'block';
      }
    } else if (!hasBaseline) {
      btnChaos.title = 'Requires baseline simulation metrics from Stage 3 for delta comparison';
      if (chaosDepAlert) {
        chaosDepAlert.className = 'alert alert-warning';
        chaosDepAlert.innerHTML = '<strong>Baseline Required:</strong> Chaos testing compares failure metrics against a baseline. Please execute Stage 3 (Baseline Simulation) before injecting failures.';
        chaosDepAlert.style.display = 'block';
      }
    } else {
      btnChaos.title = 'Inject failure scenario and measure system recovery';
      if (chaosDepAlert) chaosDepAlert.style.display = 'none';
    }
  }
}

// ============================================================================
// Presets & Form Handling
// ============================================================================

function initPresetSelector() {
  const select = document.getElementById('preset-selector');
  if (!select) return;

  select.addEventListener('change', (e) => {
    const presetKey = e.target.value;
    if (!presetKey) return;

    if (PRESET_ARCHITECTURES[presetKey]) {
      // Invalidate any previously loaded results
      invalidateArchitectureResults('Sample preset loaded. Previous simulation results cleared.');

      // Clear any pending file selection
      state.selectedFile = null;
      const dropzoneText = document.getElementById('dropzone-filename');
      if (dropzoneText) dropzoneText.textContent = 'Drop architecture diagram here or click to browse';

      // Load preset explicitly as demonstration architecture
      state.currentArchitecture = normalizeArchitectureForSimulation(JSON.parse(JSON.stringify(PRESET_ARCHITECTURES[presetKey])));
      state.architectureSource = 'sample_preset';
      state.architectureName = PRESET_ARCHITECTURES[presetKey].name;
      state.analysisProvenance = {
        provider: 'sample_preset',
        model_id: 'preset_data',
        is_mock: true,
        fallback_used: false,
      };
      state.lifecycleState = 'READY';

      populateFormFromArchitecture(state.currentArchitecture);
      updateWorkflowAvailability();
      showAlert('upload-alert', `Loaded sample preset: ${state.architectureName} [Demonstration Input]. Run Baseline Simulation in Stage 3 to model performance.`, 'info');
    }
  });
}

function populateFormFromArchitecture(arch) {
  if (!arch) return;
  const rpsInput = document.getElementById('input-rps');
  const readRatioInput = document.getElementById('input-read-ratio');
  const latencyConstraint = document.getElementById('input-max-latency');
  const budgetConstraint = document.getElementById('input-budget');

  if (rpsInput && arch.workload) rpsInput.value = arch.workload.requests_per_second;
  if (readRatioInput && arch.workload) readRatioInput.value = arch.workload.read_ratio;
  if (latencyConstraint && arch.constraints) latencyConstraint.value = arch.constraints.max_p95_latency_ms || '';
  if (budgetConstraint && arch.constraints) budgetConstraint.value = arch.constraints.max_cost_per_hour || '';
}

function initUploadDropzone() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
  });

  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });
}

function handleFileSelected(file) {
  hideAlert('upload-alert');
  const dropzoneText = document.getElementById('dropzone-filename');
  const presetSelector = document.getElementById('preset-selector');

  // Immediately invalidate previous architecture and all dependent results
  state.currentArchitecture = null;
  state.architectureSource = 'upload';
  state.architectureName = null;
  state.analysisProvenance = null;
  if (presetSelector) presetSelector.value = '';
  invalidateArchitectureResults('New diagram selected. Previous architecture and simulation results invalidated.');

  const validFormats = ['image/png', 'image/jpeg', 'image/webp'];
  const ext = file.name ? file.name.split('.').pop().toLowerCase() : '';
  const isFormatValid = validFormats.includes(file.type) || ['png', 'jpg', 'jpeg', 'webp'].includes(ext);

  if (!isFormatValid) {
    showAlert('upload-alert', `Upload rejected: Unsupported format '${file.type || ext}'. Please upload a PNG, JPEG, or WEBP diagram.`, 'danger');
    if (dropzoneText) dropzoneText.textContent = 'Upload rejected: Unsupported format (PNG, JPEG, WEBP allowed)';
    state.selectedFile = null;
    state.lifecycleState = 'ERROR';
    updateWorkflowAvailability();
    return;
  }

  const maxBytes = 10 * 1024 * 1024; // 10MB
  if (file.size > maxBytes) {
    showAlert('upload-alert', `Upload rejected: Image size (${(file.size / (1024 * 1024)).toFixed(2)} MB) exceeds maximum allowed 10 MB limit.`, 'danger');
    if (dropzoneText) dropzoneText.textContent = 'Upload rejected: File size exceeds 10MB';
    state.selectedFile = null;
    state.lifecycleState = 'ERROR';
    updateWorkflowAvailability();
    return;
  }

  state.selectedFile = file;
  state.lifecycleState = 'FILE_SELECTED';
  if (dropzoneText) {
    dropzoneText.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  }
  showAlert('upload-alert', `Diagram "${file.name}" selected. Click "Analyze & Parse Architecture" below to begin AI analysis.`, 'info');
  updateWorkflowAvailability();
}

// ============================================================================
// Actions & Workflow Execution
// ============================================================================

function initActionButtons() {
  const btnAnalyze = document.getElementById('btn-analyze');
  if (btnAnalyze) btnAnalyze.addEventListener('click', executeDiagramAnalysis);

  const btnSimulate = document.getElementById('btn-simulate');
  if (btnSimulate) btnSimulate.addEventListener('click', executeBaselineSimulation);

  const btnInvestigate = document.getElementById('btn-investigate');
  if (btnInvestigate) btnInvestigate.addEventListener('click', executeRootCauseInvestigation);

  const btnOptimize = document.getElementById('btn-optimize');
  if (btnOptimize) btnOptimize.addEventListener('click', executeOptimization);

  const btnChaos = document.getElementById('btn-chaos');
  if (btnChaos) btnChaos.addEventListener('click', executeChaosSimulation);
}

// 1. Diagram Analysis
async function executeDiagramAnalysis() {
  const btn = document.getElementById('btn-analyze');
  const requirementsInput = document.getElementById('input-requirements');
  const requirements = requirementsInput?.value?.trim() || '';

  if (!state.selectedFile && !requirements) {
    showAlert('upload-alert', 'Please upload an architecture diagram image or enter system requirements, or load a sample preset.', 'warning');
    return;
  }

  setLoading(btn, true, 'Analyzing with AI...');
  hideAlert('upload-alert');
  state.lifecycleState = 'ANALYZING';
  updateWorkflowAvailability();

  try {
    const rps = parseFloat(document.getElementById('input-rps')?.value || '1000');
    const readRatio = parseFloat(document.getElementById('input-read-ratio')?.value || '0.8');
    const writeRatio = Math.max(0, 1.0 - readRatio);

    const workload = { requests_per_second: rps, read_ratio: readRatio, write_ratio: writeRatio };
    const constraints = {
      max_p95_latency_ms: parseFloat(document.getElementById('input-max-latency')?.value || '200'),
      max_cost_per_hour: parseFloat(document.getElementById('input-budget')?.value || '2.0')
    };

    const res = await api.analyzeArchitecture({
      imageFile: state.selectedFile,
      requirements,
      workload,
      constraints
    });

    if (res && res.architecture && Array.isArray(res.architecture.components) && res.architecture.components.length > 0) {
      state.currentArchitecture = normalizeArchitectureForSimulation(res.architecture);
      state.architectureSource = 'upload';
      state.architectureName = state.selectedFile ? state.selectedFile.name : (res.architecture.architecture_id || 'Uploaded Architecture');
      state.analysisProvenance = {
        provider: res.provider,
        model_id: res.model_id,
        is_mock: res.is_mock,
        fallback_used: res.fallback_used,
      };
      state.lifecycleState = 'READY';

      // Clear any older simulation results since architecture changed
      invalidateArchitectureResults();

      updateWorkflowAvailability();

      const provenanceText = res.fallback_used
        ? `[Mode: Deterministic Fallback - Provenance: ${res.provider || 'deterministic_rules_v1'}]`
        : `[Provider: ${res.provider || 'Gemma/Gemini'}, Model: ${res.model_id || 'active_model'}]`;

      showAlert(
        'upload-alert',
        `Architecture successfully analyzed and validated (${state.currentArchitecture.components.length} components, ${state.currentArchitecture.connections.length} connections). Provenance: ${provenanceText}.`,
        'success'
      );

      // Transition to Stage 2 Topology View
      switchTab('tab-topology');
    } else {
      state.currentArchitecture = null;
      state.lifecycleState = 'ERROR';
      updateWorkflowAvailability();
      showAlert('upload-alert', `Analysis completed with validation error: ${res.status || 'invalid'}. No components detected.`, 'danger');
    }
  } catch (err) {
    state.currentArchitecture = null;
    state.lifecycleState = 'ERROR';
    updateWorkflowAvailability();
    showAlert('upload-alert', `Analysis failed: ${err.message}`, 'danger');
  } finally {
    setLoading(btn, false, 'Analyze & Parse Architecture');
  }
}

// 2. Baseline Simulation
async function executeBaselineSimulation() {
  if (!state.currentArchitecture) {
    showAlert('simulation-alert', 'Stage 3 requires a validated architecture. Complete Stage 1 (Ingest & Analyze) first.', 'warning');
    return;
  }

  const btn = document.getElementById('btn-simulate');
  setLoading(btn, true, 'Running Discrete Simulation...');
  hideAlert('simulation-alert');

  try {
    const arch = normalizeArchitectureForSimulation(state.currentArchitecture);
    const rps = parseFloat(document.getElementById('input-rps')?.value || arch.workload.requests_per_second);
    const readRatio = parseFloat(document.getElementById('input-read-ratio')?.value || arch.workload.read_ratio);

    const workloadConfig = {
      requests_per_second: rps,
      read_ratio: readRatio,
      duration_seconds: 10.0,
      pattern: "constant",
      burst_multiplier: 1.5
    };

    const constraints = arch.constraints ? {
      max_p95_latency_ms: arch.constraints.max_p95_latency_ms,
      min_throughput_rps: arch.constraints.min_throughput_rps,
      monthly_budget_usd: (arch.constraints.max_cost_per_hour || 2.0) * 730
    } : null;

    const res = await api.runBaselineSimulation({
      architecture: arch,
      workload: workloadConfig,
      constraints
    });

    state.baselineResult = res;
    renderSimulationResults(res);
    updateWorkflowAvailability(); // Enables Root-Cause and Chaos

    const modeBadge = res.simulation_metadata?.execution_mode === 'real' ? 'Real Discrete Simulation Engine' : 'Simulator Engine';
    showAlert('simulation-alert', `Baseline simulation completed successfully [${modeBadge}]. Metrics represent modeled discrete-event estimates, not production measurements.`, 'success');
  } catch (err) {
    state.baselineResult = null;
    renderSimulationResults(null);
    updateWorkflowAvailability();
    showAlert('simulation-alert', `Simulation error: ${err.message}`, 'danger');
  } finally {
    setLoading(btn, false, 'Run Baseline Simulation');
  }
}

// 3. Root-Cause Investigation
async function executeRootCauseInvestigation() {
  if (!state.currentArchitecture || !state.baselineResult) {
    showAlert('investigation-alert', 'Root-cause investigation requires an active architecture and baseline simulation evidence. Run Stage 3 first.', 'warning');
    return;
  }

  const btn = document.getElementById('btn-investigate');
  setLoading(btn, true, 'Diagnosing Bottlenecks...');
  hideAlert('investigation-alert');

  try {
    const arch = normalizeArchitectureForSimulation(state.currentArchitecture);
    const m1Arch = {
      schema_version: "1.0",
      architecture_id: arch.architecture_id || "arch-inv-01",
      components: arch.components.map(c => ({
        id: c.id,
        type: c.type,
        name: c.name || c.id,
        attributes: { cpu_cores: 2, capacity_rps: c.capacity_rps, replicas: c.replicas }
      })),
      connections: arch.connections.map(cn => ({
        source: cn.source,
        target: cn.target,
        type: "request"
      })),
      workload: {
        requests_per_second: parseFloat(document.getElementById('input-rps')?.value || arch.workload?.requests_per_second || 1000),
        read_ratio: parseFloat(document.getElementById('input-read-ratio')?.value || arch.workload?.read_ratio || 0.8),
        write_ratio: 1.0 - parseFloat(document.getElementById('input-read-ratio')?.value || arch.workload?.read_ratio || 0.8)
      },
      constraints: {
        max_p95_latency_ms: parseFloat(document.getElementById('input-max-latency')?.value || 200)
      }
    };

    const res = await api.startInvestigation({
      architecture: m1Arch,
      maxExperiments: 3
    });

    state.currentInvestigation = res;
    renderInvestigationResults(res);
    const engineBadge = res.execution_mode === 'mock' ? 'Deterministic Mock' : 'Real Discrete Simulator Engine';
    showAlert('investigation-alert', `Investigation complete [Engine: ${engineBadge}]! Tested ${res.root_cause_analysis?.experiments?.length || 0} diagnostic experiments.`, 'success');
  } catch (err) {
    state.currentInvestigation = null;
    renderInvestigationResults(null);
    showAlert('investigation-alert', `Investigation failed: ${err.message}`, 'danger');
  } finally {
    setLoading(btn, false, 'Start Root-Cause Investigation');
  }
}

// 4. Architecture Optimization
async function executeOptimization() {
  if (!state.currentArchitecture) {
    showAlert('optimization-alert', 'Stage 5 requires an analyzed architecture. Ingest an architecture first.', 'warning');
    return;
  }

  const btn = document.getElementById('btn-optimize');
  setLoading(btn, true, 'Exploring Candidates...');
  hideAlert('optimization-alert');

  try {
    const arch = normalizeArchitectureForSimulation(state.currentArchitecture);
    const objective = document.getElementById('select-objective')?.value || 'balanced';

    const workloadConfig = {
      requests_per_second: parseFloat(document.getElementById('input-rps')?.value || arch.workload.requests_per_second),
      read_ratio: parseFloat(document.getElementById('input-read-ratio')?.value || arch.workload.read_ratio),
      duration_seconds: 10.0,
      pattern: "constant"
    };

    const res = await api.runOptimization({
      architecture: arch,
      workload: workloadConfig,
      objective,
      maxCandidates: 6
    });

    state.optimizationResult = res;
    renderOptimizationResults(res);
    showAlert('optimization-alert', `Evaluated ${res.total_candidates_evaluated} candidates. Best candidate recommended under ${objective} objective.`, 'success');
  } catch (err) {
    state.optimizationResult = null;
    renderOptimizationResults(null);
    showAlert('optimization-alert', `Optimization failed: ${err.message}`, 'danger');
  } finally {
    setLoading(btn, false, 'Run Optimization Search');
  }
}

// 5. Chaos Resilience Simulation
async function executeChaosSimulation() {
  if (!state.currentArchitecture || !state.baselineResult) {
    showAlert('chaos-alert', 'Chaos testing requires an active architecture and baseline simulation metrics to compare degradation. Run Stage 3 first.', 'warning');
    return;
  }

  const btn = document.getElementById('btn-chaos');
  setLoading(btn, true, 'Injecting Fault...');
  hideAlert('chaos-alert');

  try {
    const arch = normalizeArchitectureForSimulation(state.currentArchitecture);
    const failureType = document.getElementById('select-chaos-type')?.value || 'db_slowdown';
    const targetComp = document.getElementById('select-chaos-target')?.value || (arch.components[1] ? arch.components[1].id : arch.components[0].id);

    const scenario = {
      name: `Resilience Fault: ${failureType}`,
      failure_type: failureType,
      target_component_id: failureType === 'traffic_spike' ? null : targetComp,
      start_time_sec: 2.0,
      duration_sec: 6.0,
      degradation_factor: 3.0
    };

    const workloadConfig = {
      requests_per_second: parseFloat(document.getElementById('input-rps')?.value || arch.workload.requests_per_second),
      read_ratio: parseFloat(document.getElementById('input-read-ratio')?.value || arch.workload.read_ratio),
      duration_seconds: 10.0,
      pattern: "constant"
    };

    const res = await api.runChaos({
      architecture: arch,
      workload: workloadConfig,
      scenario
    });

    state.chaosResult = res;
    renderChaosResults(res);
    showAlert('chaos-alert', `Resilience experiment complete. Compared degraded metrics against baseline.`, 'success');
  } catch (err) {
    state.chaosResult = null;
    renderChaosResults(null);
    showAlert('chaos-alert', `Chaos experiment failed: ${err.message}`, 'danger');
  } finally {
    setLoading(btn, false, 'Inject Failure & Simulate Resilience');
  }
}

// ============================================================================
// Renderers (Real Data Sources of Truth)
// ============================================================================

function renderTopology() {
  const container = document.getElementById('topology-container');
  const connSummary = document.getElementById('connection-summary');
  const chaosSelect = document.getElementById('select-chaos-target');
  const provenanceBadge = document.getElementById('topology-provenance-badge');

  if (!container) return;

  if (!state.currentArchitecture || !state.currentArchitecture.components || state.currentArchitecture.components.length === 0) {
    container.innerHTML = `
      <div class="empty-state-card" style="grid-column: 1 / -1;">
        <h3>No Architecture Topology Loaded</h3>
        <p>Upload a system architecture diagram image or select a sample preset in Stage 1 to extract and visualize active components.</p>
        <button class="btn btn-secondary" onclick="document.querySelector('.nav-tab[data-tab=\\'tab-upload\\']')?.click()">Go to Stage 1: Ingest & Analyze</button>
      </div>
    `;
    if (connSummary) {
      connSummary.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.88rem;">No active communication channels detected.</p>';
    }
    if (chaosSelect) {
      chaosSelect.innerHTML = '<option value="">No components available</option>';
    }
    if (provenanceBadge) {
      provenanceBadge.style.display = 'none';
    }
    return;
  }

  const arch = normalizeArchitectureForSimulation(state.currentArchitecture);
  container.innerHTML = '';

  if (chaosSelect) {
    chaosSelect.innerHTML = '';
  }

  // Show provenance badge
  if (provenanceBadge) {
    const prov = state.analysisProvenance;
    if (state.architectureSource === 'sample_preset') {
      provenanceBadge.textContent = 'Source: Sample Preset Input';
      provenanceBadge.style.background = 'var(--bg-lavender)';
      provenanceBadge.style.color = 'var(--color-deep)';
    } else if (prov?.fallback_used) {
      provenanceBadge.textContent = `Source: Uploaded (Deterministic Fallback: ${prov.provider || 'rules'})`;
      provenanceBadge.style.background = '#FEF3C7';
      provenanceBadge.style.color = '#B45309';
    } else {
      provenanceBadge.textContent = `Source: Uploaded (AI: ${prov?.provider || 'Gemma/Gemini'})`;
      provenanceBadge.style.background = '#DCFCE7';
      provenanceBadge.style.color = '#15803D';
    }
    provenanceBadge.style.display = 'inline-flex';
  }

  arch.components.forEach(comp => {
    const card = document.createElement('div');
    card.className = 'comp-card';
    card.innerHTML = `
      <div class="comp-header">
        <span class="comp-id">${comp.id}</span>
        <span class="comp-type-badge ${comp.type}">${comp.type}</span>
      </div>
      <div style="font-size: 0.92rem; font-weight: 700; color: var(--color-deep); margin-top: 0.25rem;">${comp.name || comp.id}</div>
      <div class="comp-stats">
        <div>Capacity: <strong>${comp.capacity_rps} RPS</strong> &times; ${comp.replicas} replica(s)</div>
        <div>Base Latency: <strong>${comp.base_latency_ms} ms</strong></div>
        <div>Cost: <strong>$${comp.cost_per_month_usd || 0}/mo</strong></div>
        ${comp.cache_hit_ratio !== undefined && comp.cache_hit_ratio !== null ? `<div>Cache Hit Ratio: <strong>${(comp.cache_hit_ratio * 100).toFixed(0)}%</strong></div>` : ''}
      </div>
    `;
    container.appendChild(card);

    if (chaosSelect) {
      const opt = document.createElement('option');
      opt.value = comp.id;
      opt.textContent = `${comp.id} (${comp.type})`;
      chaosSelect.appendChild(opt);
    }
  });

  if (connSummary) {
    if (arch.connections && arch.connections.length > 0) {
      connSummary.innerHTML = arch.connections.map(c => `
        <span style="display:inline-flex; align-items:center; gap:0.35rem; padding: 0.3rem 0.75rem; background: var(--bg-lavender); border: 1px solid var(--border-color); border-radius: var(--radius-xs); font-size: 0.85rem; margin: 0.25rem; color: var(--color-deep); font-weight: 500;">
          <code>${c.source}</code> &rarr; <code>${c.target}</code> <small style="color:var(--text-secondary)">(${c.protocol || 'http'})</small>
        </span>
      `).join('');
    } else {
      connSummary.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.88rem;">No directed connections found for this architecture.</p>';
    }
  }
}

function renderSimulationResults(res) {
  const p95El = document.getElementById('sim-p95');
  const p50El = document.getElementById('sim-p50');
  const rpsEl = document.getElementById('sim-rps');
  const costEl = document.getElementById('sim-cost');
  const breakdownContainer = document.getElementById('sim-component-breakdown');
  const bottlenecksContainer = document.getElementById('sim-bottlenecks');

  if (!res || !res.metrics) {
    if (p95El) p95El.textContent = '-- ms';
    if (p50El) p50El.textContent = '-- ms';
    if (rpsEl) rpsEl.textContent = '-- RPS';
    if (costEl) costEl.textContent = '-- /hr';
    if (breakdownContainer) {
      breakdownContainer.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">Run baseline simulation in Stage 3 to compute component-level utilization.</p>';
    }
    if (bottlenecksContainer) {
      bottlenecksContainer.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">No simulation executed yet.</p>';
    }
    return;
  }

  const m = res.metrics;
  if (p95El) p95El.textContent = `${m.p95_latency_ms.toFixed(1)} ms`;
  if (p50El) p50El.textContent = `${m.p50_latency_ms.toFixed(1)} ms`;
  if (rpsEl) rpsEl.textContent = `${m.throughput_rps.toFixed(0)} RPS`;
  if (costEl) costEl.textContent = `$${(m.total_monthly_cost_usd / 730).toFixed(2)}/hr`;

  if (breakdownContainer && m.component_breakdown) {
    breakdownContainer.innerHTML = Object.entries(m.component_breakdown).map(([id, cm]) => {
      const utilPct = Math.min(100, (cm.utilization * 100)).toFixed(1);
      const isOverloaded = cm.utilization >= 0.8;
      return `
        <div style="margin-bottom: 0.95rem;">
          <div style="display:flex; justify-content:space-between; font-size:0.88rem; margin-bottom:0.25rem;">
            <span><strong>${id}</strong> <small style="color:var(--text-secondary)">(${cm.component_type})</small></span>
            <span style="font-family:var(--font-mono); font-weight:600; color:${isOverloaded ? 'var(--color-warning)' : 'var(--color-deep)'}">${utilPct}% CPU | ${cm.total_latency_ms.toFixed(1)}ms</span>
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill ${isOverloaded ? 'warning' : ''}" style="width: ${utilPct}%"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  if (bottlenecksContainer) {
    if (res.bottlenecks && res.bottlenecks.length > 0) {
      bottlenecksContainer.innerHTML = res.bottlenecks.map(b => `
        <div class="alert alert-warning" style="margin-bottom: 0.5rem;">
          <div>
            <strong>${b.component_id}</strong> (${b.severity.toUpperCase()}): ${b.reason}
            <div style="font-size:0.82rem; margin-top:0.25rem;">Mitigation: ${b.recommended_action}</div>
          </div>
        </div>
      `).join('');
    } else {
      bottlenecksContainer.innerHTML = `<div class="alert alert-success">No capacity bottlenecks detected under baseline load.</div>`;
    }
  }
}

function renderInvestigationResults(res) {
  const hypothesesContainer = document.getElementById('investigation-hypotheses');
  const experimentsContainer = document.getElementById('investigation-experiments');

  if (!res || !res.root_cause_analysis) {
    if (hypothesesContainer) {
      hypothesesContainer.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">Formulated hypotheses will appear here once an investigation is started.</p>';
    }
    if (experimentsContainer) {
      experimentsContainer.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">Diagnostic experiments will appear here with measured metric differences.</p>';
    }
    return;
  }

  const rca = res.root_cause_analysis;

  if (hypothesesContainer && rca.hypotheses) {
    hypothesesContainer.innerHTML = rca.hypotheses.map(hyp => {
      const isConfirmed = hyp.status === 'confirmed';
      return `
        <div class="card" style="margin-bottom: 1rem; border-left: 4px solid ${isConfirmed ? 'var(--color-success)' : 'var(--color-warning)'};">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0.4rem;">
            <h4 style="font-size: 1rem; color: var(--color-deep);">${hyp.title}</h4>
            <span style="display:inline-flex; align-items:center; padding:0.25rem 0.65rem; border-radius:var(--radius-full); font-size:0.75rem; font-weight:700; background:${isConfirmed ? 'var(--color-success-bg)' : 'var(--color-warning-bg)'}; color:${isConfirmed ? 'var(--color-success)' : 'var(--color-warning)'};">${hyp.status.toUpperCase()}</span>
          </div>
          <p style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 0.6rem;">${hyp.description}</p>
          <div style="font-size: 0.82rem; color: var(--color-primary); font-weight: 500;">
            Confidence: <strong>${hyp.confidence_label.toUpperCase()}</strong> | Affected: <code>${hyp.affected_components.join(', ')}</code>
          </div>
        </div>
      `;
    }).join('');
  }

  if (experimentsContainer && rca.experiments) {
    const experimentsHtml = rca.experiments.map(exp => `
      <div style="background: var(--bg-lavender); padding: 0.85rem 1.15rem; border-radius: var(--radius-sm); margin-bottom: 0.75rem; border: 1px solid var(--border-color);">
        <div style="display:flex; justify-content:space-between; font-size:0.88rem; margin-bottom:0.35rem;">
          <strong style="color:var(--color-deep);">Experiment: ${exp.experiment_id}</strong>
          <span style="font-family:var(--font-mono); font-weight:600; color:var(--color-primary);">${exp.source} (${exp.execution_mode || 'real'})</span>
        </div>
        ${exp.diff_from_baseline.map(d => `
          <div style="font-size:0.82rem; margin-top:0.25rem; color:var(--text-main);">
            &bull; <strong>${d.metric_name}:</strong> Baseline: ${d.baseline_value}${d.unit} &rarr; Diagnostic: ${d.diagnostic_value}${d.unit}
            (${d.diff_pct !== null ? `${d.diff_pct > 0 ? '+' : ''}${d.diff_pct}%` : ''}) - <span style="color:var(--text-secondary)">${d.interpretation}</span>
          </div>
        `).join('')}
      </div>
    `).join('');

    const summaryHtml = rca.evidence_summary && rca.evidence_summary.length > 0 ? `
      <div class="card" style="margin-bottom: 1rem; background: #FAF8FF; border: 1px solid var(--border-color);">
        <strong style="color:var(--color-deep); font-size:0.95rem;">Synthesized Evidence & Root-Cause Summary:</strong>
        <div style="font-size:0.86rem; color:var(--text-main); margin-top:0.4rem;">
          ${rca.evidence_summary.map(s => `<p style="margin-bottom:0.35rem; line-height:1.45;">${s}</p>`).join('')}
        </div>
      </div>
    ` : '';

    experimentsContainer.innerHTML = summaryHtml + experimentsHtml;
  }
}

function renderOptimizationResults(res) {
  const recContainer = document.getElementById('optimization-recommended');
  const tableBody = document.getElementById('optimization-table-body');

  if (!res || !res.ranked_candidates) {
    if (recContainer) recContainer.innerHTML = '';
    if (tableBody) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--text-secondary);">No optimization candidates evaluated yet. Run optimization search to explore alternatives.</td>
        </tr>
      `;
    }
    return;
  }

  const rec = res.recommended_candidate;
  if (recContainer && rec) {
    const candidateName = rec.name || rec.candidate_id;
    recContainer.innerHTML = `
      <div class="card" style="border: 1.5px solid var(--color-success); background: #F0FDF4; margin-bottom: 1.5rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0.5rem;">
          <h3 style="color: #166534; font-size:1.15rem;">Recommended: ${candidateName}</h3>
          <span style="display:inline-flex; align-items:center; padding:0.25rem 0.65rem; border-radius:var(--radius-full); font-size:0.78rem; font-weight:700; background: #DCFCE7; color: #15803D;">Rank #1</span>
        </div>
        <p style="font-size:0.9rem; color:var(--text-main); margin-bottom:0.75rem;">${rec.description}</p>
        <div class="grid-3">
          <div class="stat-card" style="background:var(--bg-main); padding:0.75rem 1rem;">
            <div class="stat-header">p95 Latency</div>
            <div class="stat-value" style="font-size:1.35rem; color:var(--color-deep);">${rec.metrics.p95_latency_ms.toFixed(1)} ms</div>
          </div>
          <div class="stat-card" style="background:var(--bg-main); padding:0.75rem 1rem;">
            <div class="stat-header">Throughput</div>
            <div class="stat-value" style="font-size:1.35rem; color:var(--color-deep);">${rec.metrics.throughput_rps.toFixed(0)} RPS</div>
          </div>
          <div class="stat-card" style="background:var(--bg-main); padding:0.75rem 1rem;">
            <div class="stat-header">Monthly Cost</div>
            <div class="stat-value" style="font-size:1.35rem; color:var(--color-deep);">$${rec.metrics.total_monthly_cost_usd.toFixed(0)}</div>
          </div>
        </div>
        ${res.trade_off_analysis ? `
          <div style="margin-top: 0.85rem; padding: 0.75rem 1rem; background: var(--bg-main); border-radius: var(--radius-xs); border: 1px solid var(--border-color); font-size: 0.86rem; color: var(--text-main); white-space: pre-line;">
            <strong>Pareto Trade-off & AI Analysis:</strong>\n${res.trade_off_analysis}
          </div>
        ` : ''}
      </div>
    `;
  }

  if (tableBody && res.ranked_candidates) {
    tableBody.innerHTML = res.ranked_candidates.map((cand, idx) => {
      const cName = cand.name || cand.candidate_id;
      const scoreVal = cand.score !== undefined ? cand.score : (cand.objective_score !== undefined ? cand.objective_score : 1.0);
      return `
        <tr>
          <td>#${cand.rank || (idx + 1)}</td>
          <td><strong style="color:var(--color-deep);">${cName}</strong></td>
          <td><strong style="color:var(--color-primary);">${cand.metrics.p95_latency_ms.toFixed(1)} ms</strong></td>
          <td>${cand.metrics.throughput_rps.toFixed(0)} RPS</td>
          <td>$${cand.metrics.total_monthly_cost_usd.toFixed(0)}/mo</td>
          <td><span style="display:inline-flex; padding:0.2rem 0.55rem; border-radius:var(--radius-full); font-size:0.75rem; font-weight:600; background:var(--bg-lavender); color:var(--color-primary); border:1px solid var(--border-color);">Score: ${Number(scoreVal).toFixed(3)}</span></td>
        </tr>
      `;
    }).join('');
  }
}

function renderChaosResults(res) {
  const container = document.getElementById('chaos-results-container');
  if (!container) return;

  if (!res || !res.baseline_metrics || !res.failure_metrics) {
    container.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">No failure simulation executed yet. Select a fault scenario above and click Inject Failure.</p>';
    return;
  }

  const base = res.baseline_metrics;
  const fail = res.failure_metrics;

  container.innerHTML = `
    <div class="grid-3" style="margin-bottom: 1.5rem;">
      <div class="stat-card">
        <div class="stat-header">Latency Delta</div>
        <div class="stat-value ${res.latency_delta_ms > 0 ? 'delta-bad' : 'delta-good'}">
          ${res.latency_delta_ms > 0 ? '+' : ''}${res.latency_delta_ms.toFixed(1)} ms
        </div>
        <div style="font-size:0.8rem; color:var(--text-secondary)">Baseline: ${base.p95_latency_ms.toFixed(1)}ms &rarr; Degraded: ${fail.p95_latency_ms.toFixed(1)}ms</div>
      </div>
      <div class="stat-card">
        <div class="stat-header">Throughput Drop</div>
        <div class="stat-value ${res.throughput_delta_rps < 0 ? 'delta-bad' : 'delta-good'}">
          ${res.throughput_delta_rps.toFixed(0)} RPS
        </div>
        <div style="font-size:0.8rem; color:var(--text-secondary)">Baseline: ${base.throughput_rps.toFixed(0)} RPS &rarr; Degraded: ${fail.throughput_rps.toFixed(0)} RPS</div>
      </div>
      <div class="stat-card">
        <div class="stat-header">Resilience Rating</div>
        <div class="stat-value" style="color:var(--color-primary)">
          ${fail.error_rate < 0.05 ? 'RESILIENT' : 'VULNERABLE'}
        </div>
        <div style="font-size:0.8rem; color:var(--text-secondary)">Error Rate: ${(fail.error_rate * 100).toFixed(1)}%</div>
      </div>
    </div>
    <div class="alert alert-info">
      <div>
        <strong>Resilience Observation:</strong> ${res.resilience_summary || 'Component failure successfully injected and measured.'}
      </div>
    </div>
  `;
}

// ============================================================================
// Utilities
// ============================================================================

function switchTab(tabId) {
  const tabBtn = document.querySelector(`.nav-tab[data-tab="${tabId}"]`);
  if (tabBtn) tabBtn.click();
}

function setLoading(button, isLoading, text) {
  if (!button) return;
  button.disabled = isLoading;
  if (isLoading) {
    button.innerHTML = `<span class="spinner"></span> ${text}`;
  } else {
    button.textContent = text;
  }
}

function showAlert(containerId, message, type = 'info') {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.className = `alert alert-${type}`;
  container.textContent = message;
  container.style.display = 'block';
}

function hideAlert(containerId) {
  const container = document.getElementById(containerId);
  if (container) container.style.display = 'none';
}
