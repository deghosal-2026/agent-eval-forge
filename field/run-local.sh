#!/usr/bin/env bash
# Local field test runner — serial execution, resume, pagination.
#
# Usage:
#   bash field/run-local.sh --file field/list1.txt --tier cheap \
#       --endpoint https://openrouter.ai/api/v1 --model openai/gpt-4o-mini
#
#   bash field/run-local.sh --file field/list1.txt --tier local
#
#   bash field/run-local.sh --file field/list1.txt --tier cheap \
#       --endpoint https://openrouter.ai/api/v1 --model openai/gpt-4o-mini \
#       --resume --failed-only
#
#   bash field/run-local.sh --file field/list1.txt --tier better \
#       --endpoint https://openrouter.ai/api/v1 --model openai/gpt-4o \
#       --offset 10 --limit 5
#
# Secrets: API key comes from OPENROUTER_API_KEY env var. Never logged.
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS_DIR="$PROJECT_DIR/field/results"

# ── Defaults ──────────────────────────────────────────────────────────────
TIER="local"
ENDPOINT=""
MODEL_ID=""
AGENT_FILE="$PROJECT_DIR/field/list.txt"
OFFSET=0
LIMIT=0
DRY_RUN=0
RESUME=0
FAILED_ONLY=0
RUN_NOTES=""
SCENARIO_FILTER=""
FAIL_FAST=0
CLEAN=0

# ── Parse args ────────────────────────────────────────────────────────────
usage() {
  cat <<'USAGE'
Usage: field/run-local.sh --tier <local|cheap|better> --endpoint <URL> --model <MODEL> [options]

Required:
  --tier TIER            local | cheap | better
  --endpoint URL         LLM API endpoint (e.g. https://openrouter.ai/api/v1)
  --model MODEL          Model identifier (e.g. openai/gpt-4o-mini)

Agent input (choose one):
  --file PATH            Agent list file (default: field/list1.txt)
  --slug SLUG            Run a single agent by slug

Options:
  --offset N             Skip first N agents (pagination)
  --limit N              Run at most N agents (pagination)
  --scenario ID          Run only one scenario id
  --fail-fast            Stop after the first failed scenario
  --clean                 Wipe results dir before starting (default: keep)
  --resume               Skip previously passed (agent_id|scenario_id|tier|model)
  --failed-only          With --resume, only re-run previously failed
  --dry-run              Print what would run, do not execute
  -h, --help             Show this help

Environment:
  OPENROUTER_API_KEY     API key (required for cheap/better tiers). Never logged.

Notes:
  - Serial execution only (no parallelism).
  - Resume key: agent_id|scenario_id|tier|model prevents cross-tier cross-model contamination.
  - API key is redacted from all logs and artifacts.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tier) TIER="$(echo "${2:-}" | tr '[:upper:]' '[:lower:]')"; shift 2;;
    --endpoint) ENDPOINT="${2:-}"; shift 2;;
    --model) MODEL_ID="${2:-}"; shift 2;;
    --file) AGENT_FILE="${2:-}"; shift 2;;
    --slug) AGENT_SLUG="${2:-}"; shift 2;;
    --offset) OFFSET="${2:-0}"; shift 2;;
    --limit) LIMIT="${2:-0}"; shift 2;;
    --scenario) SCENARIO_FILTER="${2:-}"; shift 2;;
    --fail-fast) FAIL_FAST=1; shift;;
    --clean) CLEAN=1; shift;;
    --resume) RESUME=1; shift;;
    --failed-only) FAILED_ONLY=1; shift;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

# ── Validation ────────────────────────────────────────────────────────────
if [[ "$TIER" != "local" ]]; then
  if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo "Error: OPENROUTER_API_KEY env var required for tier '$TIER'" >&2; exit 1
  fi
  if [[ -z "$ENDPOINT" ]]; then
    echo "Error: --endpoint required for tier '$TIER'" >&2; exit 1
  fi
  if [[ -z "$MODEL_ID" ]]; then
    echo "Error: --model required for tier '$TIER'" >&2; exit 1
  fi
fi

model_label="${MODEL_ID:-mlx}"
model_safe=$(echo "$model_label" | tr '/:\\[](), ' '_______')
variant="${TIER}__${model_safe}"

# ── Load agents from file ─────────────────────────────────────────────────
if [[ -n "${AGENT_SLUG:-}" ]]; then
  AGENTS=("$AGENT_SLUG")
else
  if [[ ! -f "$AGENT_FILE" ]]; then
    echo "Error: agent file not found: $AGENT_FILE" >&2; exit 1
  fi
  AGENTS=()
  while IFS='|' read -r slug repo sha adapter cmd; do
    [[ "$slug" =~ ^# ]] && continue  # skip comment lines
    [[ -z "$slug" ]] && continue
    AGENTS+=("$slug")
  done < "$AGENT_FILE"
fi

total="${#AGENTS[@]}"

# Apply offset/limit
start=$OFFSET
if [[ "$LIMIT" -gt 0 ]]; then
  end=$((OFFSET + LIMIT))
  [[ $end -gt $total ]] && end=$total
else
  end=$total
fi

AGENTS=("${AGENTS[@]:$start:$((end-start))}")
count="${#AGENTS[@]}"

echo "=== Field Test Runner ==="
echo "File:    ${AGENT_FILE:-"(slug: $AGENT_SLUG)"}"
echo "Tier:    $TIER"
echo "Model:   ${MODEL_ID:-mlx}"
echo "Agents:  $count (offset=$OFFSET, limit=${LIMIT:-all}, total=$total)"
echo "Results: $RESULTS_DIR"
echo ""

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[dry-run] would run these agents:"
  for slug in "${AGENTS[@]}"; do
    echo "  - $slug"
  done
  exit 0
fi

# ── Resume index ──────────────────────────────────────────────────────────
COMPLETED_FILE="$RESULTS_DIR/completed.list"
INDEX_FILE="$RESULTS_DIR/index.jsonl"
mkdir -p "$RESULTS_DIR"

if [[ "$RESUME" == "1" ]]; then
  if [[ -f "$INDEX_FILE" ]]; then
    # Build completed set: agent_id|scenario_id|tier|model with status=passed
    grep '"status":"passed"' "$INDEX_FILE" | \
      grep "\"tier\":\"$TIER\"" | \
      grep "\"model\":\"$model_safe\"" | \
      sed -n 's/.*"agent_id":"\([^"]*\)".*"scenario_id":"\([^"]*\)".*/\1|\2/p' | \
      sort -u > "$COMPLETED_FILE"
    echo "[resume] loaded $(wc -l < "$COMPLETED_FILE" | tr -d ' ') completed entries"
  fi

  if [[ "$FAILED_ONLY" == "1" ]]; then
    echo "[resume] failed-only mode: running only previously non-passed entries"
  fi
fi

# ── Load scenario packs ───────────────────────────────────────────────────
SCENARIO_DIR="$PROJECT_DIR/field/scenarios"
SCENARIO_PACKS=()
if [[ -d "$SCENARIO_DIR" ]]; then
  for f in "$SCENARIO_DIR"/*.yaml; do
    [[ -f "$f" ]] && SCENARIO_PACKS+=("$(basename "$f")")
  done
fi

if [[ ${#SCENARIO_PACKS[@]} -eq 0 ]]; then
  echo "Warning: no scenario packs found in $SCENARIO_DIR" >&2
fi

echo "Scenario packs: ${SCENARIO_PACKS[*]:-(none)}"
echo ""

# ── LOCK file ─────────────────────────────────────────────────────────────
LOCK_FILE="$RESULTS_DIR/RUNNING.lock"
if [[ -f "$LOCK_FILE" ]]; then
  echo "Error: $LOCK_FILE exists — another run may be in progress." >&2
  exit 1
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE" 2>/dev/null || true' EXIT INT TERM

# ── Export env (key never logged) ────────────────────────────────────────
# set -x is never used in this script; key stays hidden
export EVALFORGE_FIELD_TIER="$TIER"
export EVALFORGE_FIELD_VARIANT="$variant"
export EVALFORGE_FIELD_CONFIG_DIR="$PROJECT_DIR/field/config"
export EVALFORGE_FIELD_AGENTS_DIR="$PROJECT_DIR/field/agents"
export EVALFORGE_FIELD_WORKER="$PROJECT_DIR/field/agent_worker.py"

  # Local tier: point agents at OMLX (ChatOpenAI-compatible)
  if [[ "$TIER" == "local" ]]; then
    export EVALFORGE_FIELD_MODEL="${MODEL_ID:-Qwen3.5-4B-4bit}"
    export EVALFORGE_FIELD_ENDPOINT="http://127.0.0.1:8000/v1"
    # Force model override in langgraph adapter to neutralize hardcoded OpenAI model names
    export EVALFORGE_FORCE_MODEL=1
    # Some PydanticAI example agents check for this gateway key at import; provide a dummy
    export PYDANTIC_AI_GATEWAY_API_KEY="local-test"
    export PYDANTIC_AI_GATEWAY_BASE_URL="https://gateway.localhost.invalid"
  fi

if [[ "$TIER" != "local" ]]; then
  export EVALFORGE_FIELD_ENDPOINT="$ENDPOINT"
  export EVALFORGE_FIELD_MODEL="$MODEL_ID"
  # Ensure the judge uses the same cloud endpoint/model unless explicitly overridden
  export EVALFORGE_FIELD_JUDGE_ENDPOINT="$ENDPOINT"
  export EVALFORGE_FIELD_JUDGE_MODEL="$MODEL_ID"
  export EVALFORGE_FIELD_MODEL_SAFE="$model_safe"
  # API key from env; never echo it
  # Map OpenRouter creds to OpenAI-compatible env so LangChain/OpenAI SDKs authenticate correctly
  # Do NOT print or log the key. setdefault is handled in adapters/worker but we prefer explicit
  # propagation here for cloud tiers so the dummy local key is never used.
  if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
    # Only set OPENAI_API_KEY if not already provided by caller
    export OPENAI_API_KEY="${OPENAI_API_KEY:-$OPENROUTER_API_KEY}"
  fi
  # Several agents and SDKs read either OPENAI_BASE_URL or OPENAI_API_BASE
  export OPENAI_BASE_URL="$ENDPOINT"
  export OPENAI_API_BASE="$ENDPOINT"

  # If a Pydantic AI Gateway API key is provided by the user, pass it through.
  # We do not synthesize a gateway key for cloud tiers.
  if [[ -n "${PYDANTIC_AI_GATEWAY_API_KEY:-}" ]]; then
    export PYDANTIC_AI_GATEWAY_API_KEY
    # Provide a reasonable default base URL if not set by the user.
    if [[ -z "${PYDANTIC_AI_GATEWAY_BASE_URL:-}" ]]; then
      export PYDANTIC_AI_GATEWAY_BASE_URL="https://gateway.ai.pydantic.dev"
    fi
  fi
fi

# ── Run per agent ─────────────────────────────────────────────────────────
passed=0
failed=0
skipped=0
overall_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)

for slug in "${AGENTS[@]}"; do
  echo "--- Agent: $slug ---"

  # Per-agent config: setup_commands + scenario_packs from field/config/<slug>.json
  AGENT_CFG="$PROJECT_DIR/field/config/$slug.json"
  AGENT_DIR="$PROJECT_DIR/field/agents/$slug"
  export EVALFORGE_FIELD_AGENT_DIR="$AGENT_DIR"
  AGENT_SETUP=()
  AGENT_PACKS=()
  AGENT_QUARANTINED=0
  if [[ -f "$AGENT_CFG" ]]; then
    while IFS= read -r cmd; do
      [[ -n "$cmd" ]] && AGENT_SETUP+=("$cmd")
    done < <(python3 -c "import json,sys; d=json.load(open('$AGENT_CFG')); [print(c) for c in d.get('setup_commands',[])]")
    while IFS= read -r pack; do
      [[ -n "$pack" ]] && AGENT_PACKS+=("$(basename "$pack")")
    done < <(python3 -c "import json,sys; d=json.load(open('$AGENT_CFG')); [print(p) for p in d.get('scenario_packs',[])]")
    # Quarantine flag
    qflag=$(python3 -c "import json;print('1' if json.load(open('$AGENT_CFG')).get('quarantined') else '0')" 2>/dev/null || echo 0)
    AGENT_QUARANTINED=$qflag
  fi

  # Run the agent's declared setup commands (e.g. uv sync) in its own directory
  if [[ ${#AGENT_SETUP[@]} -gt 0 ]]; then
    echo "  [setup] ${AGENT_SETUP[*]}"
    for _setup_cmd in "${AGENT_SETUP[@]}"; do
      (cd "$AGENT_DIR" && bash -c "$_setup_cmd" >/dev/null 2>&1) \
        || echo "  [setup] FAILED: $_setup_cmd in $AGENT_DIR"
    done
  fi

  AGENT_PYTHON=$(find "$AGENT_DIR" -path '*/.venv/bin/python' 2>/dev/null | head -1)
  AGENT_PYTHON="${AGENT_PYTHON:-uv run --directory $PROJECT_DIR python}"
  export EVALFORGE_FIELD_AGENT_PYTHON="$AGENT_PYTHON"

  # Respect the config's scenario_packs; fall back to all packs
  if [[ ${#AGENT_PACKS[@]} -gt 0 ]]; then
    ACTIVE_PACKS=()
    for p in "${SCENARIO_PACKS[@]}"; do
      for want in "${AGENT_PACKS[@]}"; do
        [[ "$p" == "$want" ]] && ACTIVE_PACKS+=("$p")
      done
    done
  else
    ACTIVE_PACKS=("${SCENARIO_PACKS[@]}")
  fi

  for pack_file in "${ACTIVE_PACKS[@]}"; do
    pack_name="${pack_file%.yaml}"

    # Read scenario IDs from the YAML pack
    scenario_ids=$(grep '^\s*- id:' "$SCENARIO_DIR/$pack_file" 2>/dev/null | sed 's/.*id: *"\(.*\)"/\1/; s/.*id: *'\''\(.*\)'\''/\1/; s/.*id: *\([^"'\''].*\)/\1/' || true)

    for sc_id in $scenario_ids; do
      if [[ -n "$SCENARIO_FILTER" && "$sc_id" != "$SCENARIO_FILTER" ]]; then
        continue
      fi
      resume_key="$slug|$sc_id|$TIER|$model_safe"

      # Resume skip check
      if [[ "$RESUME" == "1" ]]; then
        if [[ "$FAILED_ONLY" == "1" ]]; then
          # Run only if NOT in completed and WAS in index as non-passed
          if grep -qxF "$slug|$sc_id" "$COMPLETED_FILE" 2>/dev/null; then
            echo "  [skip] $sc_id (already passed)"
            skipped=$((skipped + 1))
            continue
          fi
          if ! grep -q "\"agent_id\":\"$slug\"" "$INDEX_FILE" 2>/dev/null; then
            echo "  [skip] $sc_id (no prior run, not a failure)"
            skipped=$((skipped + 1))
            continue
          fi
        else
          if grep -qxF "$slug|$sc_id" "$COMPLETED_FILE" 2>/dev/null; then
            echo "  [skip] $sc_id (already passed)"
            skipped=$((skipped + 1))
            continue
          fi
        fi
      fi

      # Run directory — wipe stale results before each scenario
      safe_slug=$(echo "$slug" | tr '/:\\[](), ' '_______')
      test_dir="$RESULTS_DIR/tests/$safe_slug/$sc_id/$variant"
      rm -rf "$test_dir"
      mkdir -p "$test_dir"

      t_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
      ts_epoch=$(date +%s)

      echo "  [$sc_id] running..."

      # If quarantined for local tier, classify as failed without executing
      if [[ "$TIER" == "local" && "$AGENT_QUARANTINED" == "1" ]]; then
        status="failed"
        reason="quarantined for local tier (infra requirement: see field/config)"
        t_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        cat > "$test_dir/result.json" <<JSON
{
  "agent_id": "$slug",
  "scenario_id": "$sc_id",
  "scenario_pack": "$pack_file",
  "tier": "$TIER",
  "model": "$model_label",
  "status": "$status",
  "started_at": "$t_start",
  "finished_at": "$t_end",
  "duration_sec": 0,
  "exit_code": 0,
  "reason": "${reason//\"/\\\"}"
}
JSON
        cat >> "$INDEX_FILE" <<JSONL
{"agent_id":"$slug","scenario_id":"$sc_id","scenario_pack":"$pack_file","tier":"$TIER","model":"$model_label","status":"$status","started_at":"$t_start","finished_at":"$t_end","duration_sec":0}
JSONL
        failed=$((failed + 1))
        echo "  [$sc_id] FAILED (quarantined) — $reason"
        continue
      fi

      # Build pytest invocation
      export EVALFORGE_FIELD_AGENT="$slug"
      export EVALFORGE_FIELD_OUTPUT_DIR="$test_dir/evalforge"
      export EVALFORGE_FIELD_PACK="$SCENARIO_DIR/$pack_file"
      export PYTHONPATH="$PROJECT_DIR/field/agents/$slug"
      PYTEST_CMD=(
        uv run pytest
        -p evalforge.pytest_plugin
        "$SCRIPT_DIR/test_field_agent.py"
        --evalforge-pack "$SCENARIO_DIR/$pack_file"
        --evalforge-agent "python:$slug.run"
        --evalforge-output "$test_dir/evalforge"
        -k "$sc_id"
      )

      # Run and capture
      exit_code=0
      "${PYTEST_CMD[@]}" >"$test_dir/console.log" 2>&1 || exit_code=$?

      t_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
      dur=$(($(date +%s) - ts_epoch))

      # Classify: parse pytest summary from console output.
      # Exit code can be 143 (SIGTERM) even when tests passed — trust the
      # pytest summary line in the console log.
      status="failed"
      if grep -qE ' [0-9]+ passed' "$test_dir/console.log" 2>/dev/null; then
        status="passed"
      elif grep -q ' 0 failed' "$test_dir/console.log" 2>/dev/null; then
        status="passed"
      elif grep -qE ' [0-9]+ skipped' "$test_dir/console.log" 2>/dev/null; then
        # Policy: skipped is fail in field trials. Treat as failed with a skip reason.
        status="failed"
      fi

      # Write result
      # Best-effort failure reason extraction for easier triage
      reason=""
      if [[ "$status" == "failed" ]]; then
        # Prefer an AssertionError line, fall back to first error-like line
        reason=$(grep -m1 -E 'AssertionError: |agent invocation failed|Error code:|No module named|must return an object' "$test_dir/console.log" | sed -E 's/^.*AssertionError: //; s/^E +//; s/\r$//' || true)
        # If still empty, see if this was actually a pytest skip and record that as failure reason
        if [[ -z "$reason" ]]; then
          reason=$(grep -m1 -E 'SKIPPED \[[0-9]+\] .+no entry point|SKIPPED \[[0-9]+\]' "$test_dir/console.log" | sed -E 's/^.*SKIPPED \[[0-9]+\] *//' || true)
          [[ -z "$reason" ]] && reason="skipped (treated as failure): no entry point or precondition not met"
        fi
      fi

      cat > "$test_dir/result.json" <<JSON
{
  "agent_id": "$slug",
  "scenario_id": "$sc_id",
  "scenario_pack": "$pack_file",
  "tier": "$TIER",
  "model": "$model_label",
  "status": "$status",
  "started_at": "$t_start",
  "finished_at": "$t_end",
  "duration_sec": $dur,
  "exit_code": $exit_code,
  "reason": "${reason//\"/\\\"}"
}
JSON

      # Append to index
      cat >> "$INDEX_FILE" <<JSONL
{"agent_id":"$slug","scenario_id":"$sc_id","scenario_pack":"$pack_file","tier":"$TIER","model":"$model_label","status":"$status","started_at":"$t_start","finished_at":"$t_end","duration_sec":$dur}
JSONL

      if [[ "$status" == "passed" ]]; then
        echo "$slug|$sc_id" >> "$COMPLETED_FILE" 2>/dev/null || true
        passed=$((passed + 1))
        echo "  [$sc_id] PASSED (${dur}s)"
      else
        failed=$((failed + 1))
        msg="  [$sc_id] FAILED (exit=$exit_code, ${dur}s)"
        [[ -n "$reason" ]] && msg+=" — $reason"
        echo "$msg"
        if [[ "$FAIL_FAST" == "1" ]]; then
          echo "  [fail-fast] stopping after first failure"
          break 3
        fi
      fi

      # Ensure evalforge dir exists even if test failed before writing
      mkdir -p "$test_dir/evalforge"
    done
  done
  echo ""
done

overall_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# ── Summary ───────────────────────────────────────────────────────────────
cat > "$RESULTS_DIR/run.json" <<RUNJSON
{
  "started_at": "$overall_start",
  "finished_at": "$overall_end",
  "tier": "$TIER",
  "model": "$model_label",
  "agents_file": "${AGENT_FILE:-slug}",
  "passed": $passed,
  "failed": $failed,
  "skipped": $skipped
}
RUNJSON

cat > "$RESULTS_DIR/summary.json" <<SUMMARY
{
  "tier": "$TIER",
  "model": "$model_label",
  "passed": $passed,
  "failed": $failed,
  "skipped": $skipped
}
SUMMARY

echo "=== Complete ==="
echo "Passed:  $passed"
echo "Failed:  $failed"
echo "Skipped: $skipped"
echo "Results: $RESULTS_DIR"
