/**
 * ArchitectIQ Reusable API Service Client
 * Handles communication with the unified FastAPI backend.
 */

// Dynamically determine API base URL from Vite env or fallback to local origin
export const API_BASE_URL = (
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  (typeof window !== 'undefined' && window.__ENV__ && window.__ENV__.VITE_API_BASE_URL) ||
  ''
).replace(/\/$/, '');

/**
 * Common request wrapper with JSON and error handling
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = options.headers || {};

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const contentType = response.headers.get('content-type') || '';
  let data = null;

  if (contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorCode = 'ERR_HTTP';

    if (typeof data === 'object' && data !== null) {
      if (data.detail) {
        if (typeof data.detail === 'string') {
          errorMessage = data.detail;
        } else if (typeof data.detail === 'object') {
          errorMessage = data.detail.message || JSON.stringify(data.detail);
          errorCode = data.detail.error_code || errorCode;
        }
      } else if (data.message) {
        errorMessage = data.message;
        errorCode = data.error_code || errorCode;
      }
    }

    const err = new Error(errorMessage);
    err.status = response.status;
    err.code = errorCode;
    err.details = data;
    throw err;
  }

  return data;
}

export const api = {
  /**
   * Health check endpoint
   */
  async checkHealth() {
    return request('/health');
  },

  /**
   * Analyze architecture diagram image and requirements
   */
  async analyzeArchitecture({ imageFile, requirements, workload, constraints }) {
    const formData = new FormData();
    if (imageFile) {
      formData.append('image', imageFile);
    }
    if (requirements) {
      formData.append('requirements', requirements);
    }
    if (workload) {
      formData.append('workload_json', JSON.stringify(workload));
    }
    if (constraints) {
      formData.append('constraints_json', JSON.stringify(constraints));
    }

    return request('/api/v1/architecture/analyze', {
      method: 'POST',
      body: formData,
    });
  },

  /**
   * Start end-to-end root-cause investigation
   */
  async startInvestigation({ architecture, maxExperiments = 3, timeoutSeconds = 60 }) {
    return request('/api/v1/investigations', {
      method: 'POST',
      body: JSON.stringify({
        architecture,
        max_diagnostic_experiments: maxExperiments,
        timeout_seconds: timeoutSeconds,
      }),
    });
  },

  /**
   * Get investigation details by ID
   */
  async getInvestigation(investigationId) {
    return request(`/api/v1/investigations/${encodeURIComponent(investigationId)}`);
  },

  /**
   * Get Member 1 handoff payload
   */
  async getHandoff(investigationId) {
    return request(`/api/v1/investigations/${encodeURIComponent(investigationId)}/handoff`);
  },

  /**
   * Run baseline discrete-event performance simulation
   */
  async runBaselineSimulation({ architecture, workload, constraints }) {
    return request('/api/simulation/run', {
      method: 'POST',
      body: JSON.stringify({
        architecture,
        workload,
        constraints: constraints || null,
      }),
    });
  },

  /**
   * Run architecture candidate generation and optimization search
   */
  async runOptimization({ architecture, workload, constraints, objective = 'balanced', maxCandidates = 6 }) {
    return request('/api/optimization/run', {
      method: 'POST',
      body: JSON.stringify({
        architecture,
        workload,
        constraints: constraints || null,
        objective,
        max_candidates: maxCandidates,
      }),
    });
  },

  /**
   * Run chaos engineering resilience experiment
   */
  async runChaos({ architecture, workload, scenario, constraints }) {
    return request('/api/chaos/run', {
      method: 'POST',
      body: JSON.stringify({
        architecture,
        workload,
        scenario,
        constraints: constraints || null,
      }),
    });
  },
};

export default api;
