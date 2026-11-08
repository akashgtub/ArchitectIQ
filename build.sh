#!/usr/bin/env bash
# ArchitectIQ Production Build Script for Render
# Ensures strict error propagation and complete frontend compilation
set -euo pipefail

echo "============================================================"
echo "ArchitectIQ: Starting Production Build"
echo "============================================================"

# Step 1: Install Python dependencies
echo ">>> [1/4] Installing Python production dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# Step 2: Install Frontend dependencies reproducibly
echo ">>> [2/4] Installing frontend dependencies via npm ci..."
if [ -f "frontend/package-lock.json" ]; then
  npm --prefix frontend ci
else
  echo "WARNING: package-lock.json not found, falling back to npm install..."
  npm --prefix frontend install
fi

# Step 3: Compile and build frontend bundle
echo ">>> [3/4] Building production frontend with Vite..."
npm --prefix frontend run build

# Step 4: Verify expected build artifacts
echo ">>> [4/4] Verifying production build artifacts..."
if [ ! -f "frontend/dist/index.html" ]; then
  echo "ERROR: Production frontend build failed! 'frontend/dist/index.html' not found." >&2
  exit 1
fi

if [ ! -d "frontend/dist/assets" ]; then
  echo "ERROR: Production frontend build failed! 'frontend/dist/assets' directory not found." >&2
  exit 1
fi

echo "============================================================"
echo "ArchitectIQ: Production Build Completed Successfully!"
echo "Artifacts generated in frontend/dist/"
echo "============================================================"
