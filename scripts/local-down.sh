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

"$DOCKER_BIN" compose -f "$ROOT_DIR/docker-compose.local.yml" down
