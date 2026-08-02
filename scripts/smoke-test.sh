#!/usr/bin/env bash
# Smoke test: run 1 scenario through each adapter with a real LLM.
# Skips if OPENAI_API_KEY is not set.
# Usage: bash scripts/smoke-test.sh
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "[SKIP] OPENAI_API_KEY not set — smoke test requires a real LLM"
    exit 0
fi

MODEL="${SMOKE_MODEL:-openai/gpt-4o-mini}"
PASS=0
FAIL=0

run_test() {
    local label="$1" adapter="$2" module="$3" func="${4:-build_agent}"
    echo -n "[$label] "
    if uv run evalforge run \
        --pack scenarios/core-launch.yaml \
        --agent "$adapter:$module:$func" \
        --judge "$MODEL" \
        --scenario launch-01-account-policy \
        --quiet \
        --timeout 60 >/dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        PASS=$((PASS+1))
    else
        echo -e "${RED}FAIL${NC}"
        FAIL=$((FAIL+1))
    fi
}

echo "=== EvalForge Smoke Test ==="
echo "Model: $MODEL"
echo ""

run_test "Python (quickstart)" "python" "examples.quickstart_agent" "run"
run_test "LangGraph" "langgraph" "examples.langgraph_agent" "build_agent"
run_test "PydanticAI" "pydantic-ai" "examples.pydantic_ai_agent" "build_agent"

echo ""
echo "=== Results ==="
echo "Passed: $PASS"
echo "Failed: $FAIL"

if [[ $FAIL -gt 0 ]]; then
    echo "Some tests failed. Check the output above."
    exit 1
fi

echo "All smoke tests passed!"
