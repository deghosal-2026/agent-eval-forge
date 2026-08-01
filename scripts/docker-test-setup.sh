#!/usr/bin/env bash
# Docker test setup script — fully automated lifecycle.
# Builds a fresh image from the project Dockerfile, then runs the Docker test suite.
# Usage: bash scripts/docker-test-setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="${EVALFORGE_DOCKER_IMAGE:-evalforge-agent-runner}"

echo "=== Step 1: Remove old Docker image ($IMAGE_NAME) ==="
docker rmi "$IMAGE_NAME" --force 2>/dev/null || true

echo "=== Step 2: Build fresh Docker image ==="
docker build -t "$IMAGE_NAME" -f "$PROJECT_DIR/Dockerfile" "$PROJECT_DIR"

echo "=== Step 3: Run Docker integration tests ==="
cd "$PROJECT_DIR"
uv run pytest tests/test_security_container_integration.py -m docker -v

echo "=== Docker tests complete ==="