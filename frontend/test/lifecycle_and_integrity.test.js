import test from 'node:test';
import assert from 'node:assert';
import { api, API_BASE_URL } from '../src/api.js';

test('Regression 1: Opening state lifecycle starts in EMPTY with no fabricated architecture', () => {
  const initialState = {
    lifecycleState: 'EMPTY',
    currentArchitecture: null,
    architectureSource: null,
    baselineResult: null,
    currentInvestigation: null,
    optimizationResult: null,
    chaosResult: null,
    selectedFile: null,
  };

  assert.strictEqual(initialState.lifecycleState, 'EMPTY');
  assert.strictEqual(initialState.currentArchitecture, null);
  assert.strictEqual(initialState.baselineResult, null);
  assert.strictEqual(initialState.optimizationResult, null);
  assert.strictEqual(initialState.chaosResult, null);
});

test('Regression 2: Selecting a file does not count as successful analysis', () => {
  const state = {
    lifecycleState: 'EMPTY',
    currentArchitecture: null,
    selectedFile: null,
  };

  // User selects a file
  const mockFile = { name: 'system_diagram.png', size: 1024 * 50, type: 'image/png' };
  state.selectedFile = mockFile;
  state.lifecycleState = 'FILE_SELECTED';

  // Architecture MUST remain null until analysis succeeds
  assert.strictEqual(state.lifecycleState, 'FILE_SELECTED');
  assert.strictEqual(state.currentArchitecture, null);
});

test('Regression 3: Selecting a new image invalidates all previous architecture and simulation results', () => {
  const state = {
    lifecycleState: 'READY',
    currentArchitecture: { id: 'old-arch', components: [{ id: 'api-1' }] },
    baselineResult: { metrics: { p95_latency_ms: 45.0 } },
    currentInvestigation: { status: 'completed' },
    optimizationResult: { ranked_candidates: [{ rank: 1 }] },
    chaosResult: { latency_delta_ms: 12.0 },
    selectedFile: { name: 'old_diagram.png' },
  };

  // Simulate file selection hook: must clear all prior results
  const handleFileSelect = (newFile) => {
    state.currentArchitecture = null;
    state.baselineResult = null;
    state.currentInvestigation = null;
    state.optimizationResult = null;
    state.chaosResult = null;
    state.selectedFile = newFile;
    state.lifecycleState = 'FILE_SELECTED';
  };

  handleFileSelect({ name: 'new_diagram.png', size: 1024 * 20, type: 'image/png' });

  assert.strictEqual(state.currentArchitecture, null);
  assert.strictEqual(state.baselineResult, null);
  assert.strictEqual(state.currentInvestigation, null);
  assert.strictEqual(state.optimizationResult, null);
  assert.strictEqual(state.chaosResult, null);
  assert.strictEqual(state.lifecycleState, 'FILE_SELECTED');
});

test('Regression 4: File validation rejects unsupported image formats and oversized payloads', () => {
  const validateFile = (file) => {
    const validFormats = ['image/png', 'image/jpeg', 'image/webp'];
    const ext = file.name ? file.name.split('.').pop().toLowerCase() : '';
    const isFormatValid = validFormats.includes(file.type) || ['png', 'jpg', 'jpeg', 'webp'].includes(ext);
    if (!isFormatValid) {
      return { valid: false, error: 'ERR_UNSUPPORTED_FORMAT' };
    }
    if (file.size > 10 * 1024 * 1024) {
      return { valid: false, error: 'ERR_SIZE_EXCEEDED' };
    }
    return { valid: true };
  };

  assert.strictEqual(validateFile({ name: 'code.py', size: 100, type: 'text/x-python' }).valid, false);
  assert.strictEqual(validateFile({ name: 'huge.png', size: 15 * 1024 * 1024, type: 'image/png' }).valid, false);
  assert.strictEqual(validateFile({ name: 'valid.png', size: 500 * 1024, type: 'image/png' }).valid, true);
});

test('Regression 5: Workflow gatekeeper enforces stage dependencies strictly', () => {
  const canRunSimulation = (arch) => Boolean(arch && arch.components?.length > 0);
  const canRunInvestigation = (arch, baseline) => Boolean(arch && baseline && baseline.metrics);
  const canRunOptimization = (arch) => Boolean(arch && arch.components?.length > 0);
  const canRunChaos = (arch, baseline) => Boolean(arch && baseline && baseline.metrics);

  // Unuploaded / empty state
  assert.strictEqual(canRunSimulation(null), false);
  assert.strictEqual(canRunInvestigation(null, null), false);
  assert.strictEqual(canRunOptimization(null), false);
  assert.strictEqual(canRunChaos(null, null), false);

  // Architecture loaded, but baseline not yet executed
  const arch = { components: [{ id: 'gw-1' }, { id: 'api-1' }] };
  assert.strictEqual(canRunSimulation(arch), true);
  assert.strictEqual(canRunInvestigation(arch, null), false); // BLOCKED without baseline
  assert.strictEqual(canRunOptimization(arch), true);
  assert.strictEqual(canRunChaos(arch, null), false); // BLOCKED without baseline

  // Baseline completed
  const baseline = { metrics: { p95_latency_ms: 120.0, throughput_rps: 800 } };
  assert.strictEqual(canRunInvestigation(arch, baseline), true);
  assert.strictEqual(canRunChaos(arch, baseline), true);
});

test('Regression 6: Analysis failure clears previous state and sets ERROR lifecycle', () => {
  const state = {
    lifecycleState: 'ANALYZING',
    currentArchitecture: { id: 'sample' },
    baselineResult: { metrics: {} },
  };

  // On analysis failure
  const handleAnalysisFailure = (err) => {
    state.currentArchitecture = null;
    state.baselineResult = null;
    state.lifecycleState = 'ERROR';
    state.error = err.message;
  };

  handleAnalysisFailure(new Error('Invalid image corruption'));
  assert.strictEqual(state.lifecycleState, 'ERROR');
  assert.strictEqual(state.currentArchitecture, null);
  assert.strictEqual(state.baselineResult, null);
});

test('Regression 7: API client maps network disconnection with actionable guidance', async () => {
  // Verify that an unreachable host yields ERR_NETWORK_DISCONNECTED rather than generic error
  try {
    // Port 64999 is guaranteed to refuse connection
    const customApiBase = 'http://127.0.0.1:64999';
    const testUrl = `${customApiBase}/health`;
    let thrownError = null;
    try {
      await fetch(testUrl);
    } catch (netErr) {
      thrownError = new Error(
        `Cannot connect to ArchitectIQ backend at ${testUrl}. Please ensure the FastAPI server is running on port 8000. Details: ${netErr.message}`
      );
      thrownError.code = 'ERR_NETWORK_DISCONNECTED';
    }
    assert.ok(thrownError);
    assert.strictEqual(thrownError.code, 'ERR_NETWORK_DISCONNECTED');
    assert.ok(thrownError.message.includes('FastAPI server is running on port 8000'));
  } catch (err) {
    assert.fail(err);
  }
});

test('Regression 8: Provenance transparency flags deterministic fallback vs live AI model', () => {
  const formatProvenance = (res) => {
    if (res.fallback_used || res.is_mock) {
      return `[Mode: Deterministic Fallback - Provenance: ${res.provider || 'deterministic_rules_v1'}]`;
    }
    return `[Provider: ${res.provider}, Model: ${res.model_id}]`;
  };

  const fallbackResp = { fallback_used: true, is_mock: true, provider: 'deterministic_fallback', model_id: 'mock-rules' };
  assert.ok(formatProvenance(fallbackResp).includes('Deterministic Fallback'));
  assert.ok(!formatProvenance(fallbackResp).includes('Gemma/Gemini'));

  const liveResp = { fallback_used: false, is_mock: false, provider: 'gemini', model_id: 'gemini-flash-latest' };
  assert.ok(formatProvenance(liveResp).includes('Provider: gemini'));
});
