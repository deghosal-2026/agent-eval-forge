#!/usr/bin/env bash
# Docker test setup script — requires a prebuilt image, then runs the Docker test suite.
# Usage: bash scripts/docker-test-setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="${EVALFORGE_DOCKER_IMAGE:-evalforge-agent-runner}"

echo "=== Step 1: Ensure Docker image '$IMAGE_NAME' exists ==="
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Error: required image '$IMAGE_NAME' not found. Build or load it explicitly before running docker tests." >&2
  exit 1
fi

echo "=== Step 2: Run Docker integration tests ==="
cd "$PROJECT_DIR"
uv run pytest -m docker -v \
  tests/test_security_container_integration.py \
  tests/test_security_docker_llm.py

echo "=== Docker tests complete ==="
