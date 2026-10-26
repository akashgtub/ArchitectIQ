/**
 * ArchitectIQ Reusable API Service Client
 * Handles communication with the unified FastAPI backend.
 */

// Dynamically determine API base URL from Vite env, window config, or fallback to backend origin
export const API_BASE_URL = (
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  (typeof window !== 'undefined' && window.__ENV__ && window.__ENV__.VITE_API_BASE_URL) ||
  (typeof window !== 'undefined' && window.location && window.location.port !== '8000' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'http://127.0.0.1:8000' : '')
).replace(/\/$/, '');

/**
 * Common request wrapper with network catch, JSON parsing, and detailed error extraction
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = options.headers || {};

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (networkErr) {
    const error = new Error(
      `Cannot connect to ArchitectIQ backend at ${url}. Please ensure the FastAPI server is running on port 8000 (run: uvicorn backend.main:app). Details: ${networkErr.message}`
    );
    error.status = 0;
    error.code = 'ERR_NETWORK_DISCONNECTED';
    error.details = { originalError: networkErr.message, url };
    throw error;
  }

  const contentType = response.headers.get('content-type') || '';
  let data = null;

  try {
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }
  } catch (parseErr) {
    data = null;
  }

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let errorCode = `ERR_HTTP_${response.status}`;

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
    } else if (typeof data === 'string' && data.trim()) {
      errorMessage = data.slice(0, 300);
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
