#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -x "$ROOT_DIR/backend/.venv/bin/python" ]; then
  python3.12 -m venv "$ROOT_DIR/backend/.venv"
fi

"$ROOT_DIR/backend/.venv/bin/python" -m pip install --disable-pip-version-check -r "$ROOT_DIR/backend/requirements-dev.txt"

(
  cd "$ROOT_DIR/backend"
  source .venv/bin/activate
  pytest
)

(
  cd "$ROOT_DIR/frontend"
  npm run build
)

