#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_BIN="${DOCKER_BIN:-}"
DOCKER_DESKTOP_BIN="/Applications/Docker.app/Contents/Resources/bin"

if [ -d "$DOCKER_DESKTOP_BIN" ]; then
  export PATH="$DOCKER_DESKTOP_BIN:$PATH"
fi

if [ -z "$DOCKER_BIN" ] && command -v docker >/dev/null 2>&1; then
  DOCKER_BIN="$(command -v docker)"
fi
if [ -z "$DOCKER_BIN" ] && [ -x "$DOCKER_DESKTOP_BIN/docker" ]; then
  DOCKER_BIN="$DOCKER_DESKTOP_BIN/docker"
fi
if [ -z "$DOCKER_BIN" ]; then
  echo "docker command not found. Install Docker Desktop or add the Docker CLI to PATH." >&2
  exit 127
fi

"$DOCKER_BIN" compose -f "$ROOT_DIR/docker-compose.local.yml" up -d

echo "Waiting for FastAPI local backend on http://localhost:8001/health ..."
for _ in $(seq 1 90); do
  if curl -fsS "http://localhost:8001/health" >/dev/null 2>&1; then
    echo "Local stack is ready."
    echo "Frontend: http://localhost:5173"
    echo "Backend:  http://localhost:8001"
    exit 0
  fi
  sleep 2
done

echo "Local backend did not become healthy in time." >&2
"$DOCKER_BIN" compose -f "$ROOT_DIR/docker-compose.local.yml" logs backend >&2
exit 1
