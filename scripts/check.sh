#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "Bright Smile Dental Voice Assistant Check"
echo "========================================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "1. Checking required documentation..."
for doc in README.md DESIGN.md AI_USAGE.md; do
  if [ ! -f "$ROOT_DIR/$doc" ]; then
    echo "ERROR: Missing $doc"
    exit 1
  fi
done
if [ -z "$(ls -A "$ROOT_DIR/docs/ai-usage" 2>/dev/null)" ]; then
  echo "ERROR: docs/ai-usage/ must not be empty"
  exit 1
fi
echo "✓ Documentation checks passed"

echo "2. Checking for committed secrets..."
if grep -rnEI --exclude-dir={.git,node_modules,.next,.venv,__pycache__} \
  "AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z-_]{35}|sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{36}" "$ROOT_DIR" 2>/dev/null; then
  echo "ERROR: Potential secrets found!"
  exit 1
fi
echo "✓ Secrets check passed"

echo "3. Running backend tests..."
export PYTHONPATH="$ROOT_DIR/backend/src"
python -m pytest "$ROOT_DIR/backend/tests"
echo "✓ Backend tests passed"

echo "4. Running frontend tests..."
cd "$ROOT_DIR/frontend"
npm run test
echo "✓ Frontend tests passed"

echo "========================================="
echo "ALL GATES PASSED!"
echo "========================================="
