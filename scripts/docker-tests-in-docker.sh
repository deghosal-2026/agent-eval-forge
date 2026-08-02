#!/usr/bin/env bash
# Run the Docker isolation tests inside a prebuilt Linux image. The container is
# granted access to the host Docker daemon via /var/run/docker.sock so inner
# tests can launch containers.
#
# Usage: bash scripts/docker-tests-in-docker.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="${EVALFORGE_DOCKER_IMAGE:-evalforge-agent-runner}"
PLATFORM="${EVALFORGE_DOCKER_PLATFORM:-linux/amd64}"

# Create timestamped results directory
TS="$(date +%Y%m%d-%H%M%S)"
RESULTS_DIR="$PROJECT_DIR/test-results/docker/$TS"
mkdir -p "$RESULTS_DIR"
ln -snf "$RESULTS_DIR" "$PROJECT_DIR/test-results/docker/latest"

echo "=== Step 1: Ensure Docker is available ==="
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker CLI not found. Install Docker and try again." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker daemon not running or not accessible. Start Docker and retry." >&2
  exit 1
fi

echo "=== Step 2: Ensure image '$IMAGE_NAME' exists ==="
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Error: required image '$IMAGE_NAME' not found. Build or load it explicitly before running docker tests." >&2
  exit 1
fi

cleanup() {
  echo "Artifacts saved under: $RESULTS_DIR"
}
trap cleanup EXIT INT TERM

echo "=== Step 3: Run docker isolation tests inside the container ==="
# We run tests from /app (the project is already copied into the image) and use uv
# to ensure the synced environment is leveraged. We mount the Docker socket so the
# inner tests can invoke `docker run` to start sandboxed containers.
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$RESULTS_DIR":/results \
  -e EVALFORGE_DOCKER_IMAGE="$IMAGE_NAME" \
  "$IMAGE_NAME" \
  bash -lc '
    set -euo pipefail
    cd /app
    # Install pytest HTML plugin into the uv-managed environment
    uv pip install --quiet pytest-html pytest-metadata
    # Generate a single self-contained HTML report; no other artifacts
    uv run pytest -m docker -vv \
      --html=/results/report.html --self-contained-html \
      tests/test_security_container_integration.py \
      tests/test_security_docker_llm.py
  '

echo "=== Docker-in-Docker tests complete ==="

# Post-run: remove any files except the HTML report to avoid storing sensitive info
if [ -d "$RESULTS_DIR" ]; then
  find "$RESULTS_DIR" -mindepth 1 -not -name 'report.html' -exec rm -rf {} + 2>/dev/null || true
fi

# Post-run: remove all other docker test-results entries except the latest symlink and this run's folder
DOCKER_RESULTS_DIR="$PROJECT_DIR/test-results/docker"
if [ -d "$DOCKER_RESULTS_DIR" ]; then
  for entry in "$DOCKER_RESULTS_DIR"/*; do
    base="$(basename "$entry")"
    # keep the canonical symlink and the current timestamped directory
    if [ "$base" = "latest" ] || [ "$base" = "$TS" ]; then
      continue
    fi
    rm -rf "$entry" 2>/dev/null || true
  done
fi
