#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo 'Usage: ./scripts/change-local-admin-password.sh admin@example.com "New-Strong-Local-Password-123!"' >&2
  exit 64
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_BIN="${DOCKER_BIN:-}"
DOCKER_DESKTOP_BIN="/Applications/Docker.app/Contents/Resources/bin"
PYTHON_BIN="${ROOT_DIR}/backend/.venv/bin/python"

if [ -d "$DOCKER_DESKTOP_BIN" ]; then
  export PATH="$DOCKER_DESKTOP_BIN:$PATH"
fi

if [ -z "$DOCKER_BIN" ] && command -v docker >/dev/null 2>&1; then
  DOCKER_BIN="$(command -v docker)"
fi
if [ -z "$DOCKER_BIN" ] && [ -x "$DOCKER_DESKTOP_BIN/docker" ]; then
  DOCKER_BIN="$DOCKER_DESKTOP_BIN/docker"
fi
if [ -n "$DOCKER_BIN" ]; then
  BACKEND_CONTAINER="$("$DOCKER_BIN" compose -f "$ROOT_DIR/docker-compose.local.yml" ps -q backend 2>/dev/null || true)"
  if [ -n "$BACKEND_CONTAINER" ]; then
    "$DOCKER_BIN" compose -f "$ROOT_DIR/docker-compose.local.yml" exec -T backend python -m local_app.admin_cli change-password "$1" "$2"
    exit $?
  fi
fi

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3.12"
fi

PYTHONPATH="$ROOT_DIR/backend/src" "$PYTHON_BIN" -m local_app.admin_cli change-password "$1" "$2"
