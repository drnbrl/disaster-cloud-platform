#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="${LOCAL_API_URL:-http://localhost:8001}"
COUNT="${1:-15}"
PYTHON_BIN="${ROOT_DIR}/backend/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3.12"
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/seed_requests.py" --api-url "$API_URL" --count "$COUNT"

