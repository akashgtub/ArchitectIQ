import test from 'node:test';
import assert from 'node:assert';
import { api, API_BASE_URL } from '../src/api.js';

test('API client exports essential methods', () => {
  assert.strictEqual(typeof api.checkHealth, 'function');
  assert.strictEqual(typeof api.analyzeArchitecture, 'function');
  assert.strictEqual(typeof api.startInvestigation, 'function');
  assert.strictEqual(typeof api.getInvestigation, 'function');
  assert.strictEqual(typeof api.getHandoff, 'function');
  assert.strictEqual(typeof api.runBaselineSimulation, 'function');
  assert.strictEqual(typeof api.runOptimization, 'function');
  assert.strictEqual(typeof api.runChaos, 'function');
  assert.strictEqual(typeof api.listPresets, 'function');
  assert.strictEqual(typeof api.getPreset, 'function');
  assert.strictEqual(typeof api.listSavedArchitectures, 'function');
  assert.strictEqual(typeof api.saveArchitecture, 'function');
  assert.strictEqual(typeof api.getSavedArchitecture, 'function');
  assert.strictEqual(typeof api.deleteSavedArchitecture, 'function');
  assert.strictEqual(typeof api.listSimulations, 'function');
  assert.strictEqual(typeof api.getSimulation, 'function');
});

test('API client defaults to relative URL or configured base', () => {
  assert.ok(typeof API_BASE_URL === 'string');
});
