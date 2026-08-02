#!/usr/bin/env bash
# Local runner for Docker isolation tests.
# - Requires a prebuilt evalforge-agent-runner image
# - Allows running on macOS by setting EVALFORGE_DOCKER_ALLOW_DARWIN=1
# - Ensures local imports work by setting PYTHONPATH=src
#
# Usage: bash scripts/docker-tests-local.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="${EVALFORGE_DOCKER_IMAGE:-evalforge-agent-runner}"

echo "=== Checking docker CLI and daemon ==="
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker CLI not found. Install Docker and try again." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker daemon not running or not accessible. Start Docker Desktop/daemon and retry." >&2
  exit 1
fi

echo "=== Ensuring image '$IMAGE_NAME' exists ==="
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Error: required image '$IMAGE_NAME' not found. Build or load it explicitly before running docker tests." >&2
  exit 1
else
  echo "Image '$IMAGE_NAME' already present; skipping build."
fi

echo "=== Running Docker isolation tests ==="
cd "$PROJECT_DIR"

# Allow macOS hosts to run these for smoke checks (isolation semantics differ).
export EVALFORGE_DOCKER_ALLOW_DARWIN=${EVALFORGE_DOCKER_ALLOW_DARWIN:-1}

# Make local package importable without installing deps.
export PYTHONPATH="$PROJECT_DIR/src:${PYTHONPATH:-}"

set -x
pytest -m docker -v \
  tests/test_security_container_integration.py \
  tests/test_security_docker_llm.py
set +x

echo "=== Done ==="
