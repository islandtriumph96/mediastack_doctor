#!/usr/bin/env bash
set -euo pipefail

echo "🔍 MediaStack Doctor - Development Check"
echo "========================================"

echo "📋 Python version:"
python3 -V

echo "🧹 Uninstalling any existing mediastack-doctor..."
pip3 uninstall -y mediastack-doctor || true

echo "📦 Installing in editable mode..."
pip3 install -e .

echo "✅ Testing imports..."
python3 -c "import mediastack_doctor, mediastack_doctor.cli; print('import_ok')"

echo "🔧 Testing module runner..."
python3 -m mediastack_doctor --help

echo "🚀 Testing console script..."
mediastack-doctor --help

echo "💨 Running smoke test..."
python3 scripts/smoke_run.py

echo "🎉 All checks passed!"
