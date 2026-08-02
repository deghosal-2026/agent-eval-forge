#!/usr/bin/env bash
# Local field test runner (serial only).
#
# Runs the field test suite with single-worker execution on a developer machine.
# Supports:
# - MLX local tier (no API keys)
# - Cloud tier via OpenRouter (user supplies key and model on CLI)
#
# Examples:
#   # Local MLX sweep
#   bash scripts/field-run-local.sh --tier local
#
#   # Cheap cloud sweep (OpenRouter, gpt-4o-mini)
#   bash scripts/field-run-local.sh --tier cheap \
#        --key "$OPENROUTER_API_KEY" \
#        --model openai/gpt-4o-mini
#
#   # Better cloud sweep (OpenRouter, gpt-4o)
#   bash scripts/field-run-local.sh --tier better \
#        --key "$OPENROUTER_API_KEY" \
#        --model openai/gpt-4o
#
# You can also scope to specific agents:
#   bash scripts/field-run-local.sh --tier local --agents langgraph-a,pydantic-b
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage: field-run-local.sh --tier <local|cheap|better|custom> [--key <OPENROUTER_KEY>] [--model <MODEL_ID>] [--agents <comma_list>] [--refresh]\
                          [--results <dir>] [--notes <text>] [--resume <latest|path>] [--failed-only]

Options:
  --tier TIER        One of: local | cheap | better | custom
  --key KEY          OpenRouter API key (required for non-local tiers)
  --model MODEL      Cloud model identifier (e.g., openai/gpt-4o-mini). Required for cloud tiers.
  --agents LIST      Comma-separated agent_ids to run (default: all configured field agents)
  --refresh          Re-clone agents per field/setup.sh policy (if implemented)
  --results DIR      Results root directory (default: field/results/<timestamp>)
  --notes TEXT       Freeform run notes to include in run.json
  --resume ARG       Resume from 'latest' or a specific results folder path (skips completed cases)
  --failed-only      When resuming, run only cases that previously failed or timed out
  -h, --help         Show this help

Notes:
  - Serial execution only (no test parallelism).
  - For cloud tiers, this script exports OPENAI_API_KEY=<OpenRouterKey> and OPENAI_BASE_URL=https://openrouter.ai/api/v1 for compatibility.
  - Also exports OPENROUTER_API_KEY=<OpenRouterKey>, EVALFORGE_FIELD_MODEL=<MODEL>, and MODEL=<MODEL> for broader agent compatibility.
USAGE
}

TIER=""
OPENROUTER_KEY=""
MODEL_ID=""
AGENTS_CSV=""
REFRESH="0"
RESULTS_DIR=""
RUN_NOTES=""
RESUME_ARG=""
FAILED_ONLY="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tier) TIER="${2:-}"; shift 2;;
    --key) OPENROUTER_KEY="${2:-}"; shift 2;;
    --model) MODEL_ID="${2:-}"; shift 2;;
    --agents) AGENTS_CSV="${2:-}"; shift 2;;
    --refresh) REFRESH="1"; shift;;
    --results) RESULTS_DIR="${2:-}"; shift 2;;
    --notes) RUN_NOTES="${2:-}"; shift 2;;
    --resume) RESUME_ARG="${2:-}"; shift 2;;
    --failed-only) FAILED_ONLY="1"; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

if [[ -z "$TIER" ]]; then
  echo "Error: --tier is required" >&2
  usage; exit 1
fi

case "$TIER" in
  local)
    : # no API key or model needed
    ;;
  cheap|better|custom)
    if [[ -z "$OPENROUTER_KEY" ]]; then
      echo "Error: --key is required for tier '$TIER'" >&2
      exit 1
    fi
    if [[ -z "$MODEL_ID" ]]; then
      echo "Error: --model is required for tier '$TIER'" >&2
      exit 1
    fi
    ;;
  *)
    echo "Error: invalid --tier '$TIER' (expected local|cheap|better|custom)" >&2
    exit 1
    ;;
esac

export EVALFORGE_FIELD_MODEL_TIER="$TIER"

if [[ "$TIER" != "local" ]]; then
  # Configure OpenRouter as an OpenAI-compatible endpoint for broad agent compatibility.
  export OPENROUTER_API_KEY="$OPENROUTER_KEY"
  export OPENAI_API_KEY="$OPENROUTER_KEY"
  export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
  export EVALFORGE_FIELD_MODEL="$MODEL_ID"
  export MODEL="$MODEL_ID"
fi

cd "$PROJECT_DIR"

# Determine results directory
timestamp() { date +%Y%m%d-%H%M%S; }

if [[ -n "$RESUME_ARG" ]]; then
  if [[ "$RESUME_ARG" == "latest" ]]; then
    if [[ -L "$PROJECT_DIR/field/results/latest" ]]; then
      RESULTS_DIR="$(readlink "$PROJECT_DIR/field/results/latest")"
      # Resolve relative symlink to absolute
      [[ "$RESULTS_DIR" != /* ]] && RESULTS_DIR="$PROJECT_DIR/field/results/$RESULTS_DIR"
    else
      echo "Error: no latest symlink at field/results/latest" >&2; exit 1
    fi
  else
    RESULTS_DIR="$RESUME_ARG"
  fi
  if [[ ! -d "$RESULTS_DIR" ]]; then
    echo "Error: resume path not found: $RESULTS_DIR" >&2; exit 1
  fi
else
  if [[ -z "$RESULTS_DIR" ]]; then
    RESULTS_DIR="$PROJECT_DIR/field/results/$(timestamp)"
  fi
  mkdir -p "$RESULTS_DIR"
  ln -snf "$RESULTS_DIR" "$PROJECT_DIR/field/results/latest"
fi

# Write a short README for this run directory
cat > "$RESULTS_DIR/README.md" <<README
# Field Test Run

This folder holds a single local field-test run.

- run.json: metadata for the run
- summary.json: quick counts and pointers
- manifest.json: deterministic list of planned tests (nodeid, tier, model)
- index.jsonl: one JSON object per executed testcase variant
- tests/: per-testcase folders; each has tier+model variants side-by-side

Per-test layout under tests/<safe_nodeid>/:
- <tier>__<model_safe>/
  - result.json: status, timings, tier, model, logdir
  - console.log: stdout/stderr for that testcase variant
  - evalforge/: normalized I/O (prompt.txt, completion.txt, envelope.json, etc.) if available
  - scores.json: scorers per testcase (if available)
  - artifacts/: extra files created by the testcase (optional)

Notes:
- Local-only; do not commit to git. Secrets must not be persisted.
- Variants do not cross-skip in resume; keys are (nodeid, tier, model).
README

# Create RUNNING.lock to prevent concurrent writes into the same folder
LOCK_FILE="$RESULTS_DIR/RUNNING.lock"
if [[ -e "$LOCK_FILE" ]]; then
  echo "Error: found $LOCK_FILE — another run may be writing to this folder. Remove it to proceed." >&2
  exit 1
fi
trap 'rm -f "$LOCK_FILE" >/dev/null 2>&1 || true' EXIT INT TERM
echo $$ > "$LOCK_FILE"

# Optional pre-step: clone/setup agents if the harness exists (only for fresh runs)
if [[ "$REFRESH" == "1" && -x "$PROJECT_DIR/field/setup.sh" ]]; then
  if [[ -n "$AGENTS_CSV" ]]; then
    bash "$PROJECT_DIR/field/setup.sh" --refresh --agent "${AGENTS_CSV}"
  else
    bash "$PROJECT_DIR/field/setup.sh" --refresh
  fi
fi

echo "=== Running field tests (serial) ==="
set -x

PYTEST_ARGS=("field/")

if [[ -n "$AGENTS_CSV" ]]; then
  PYTEST_ARGS+=("--field-agents" "$AGENTS_CSV")
fi

# Always run serially; do not enable xdist. Be explicit with markers if registered.
# Build deterministic manifest via pytest collection
COLLECT_ARGS=("${PYTEST_ARGS[@]}" -m field --collect-only -q)
if [[ -n "$AGENTS_CSV" ]]; then
  COLLECT_ARGS+=("--field-agents" "$AGENTS_CSV")
fi

mapfile -t NODEIDS < <(uv run pytest "${COLLECT_ARGS[@]}" | sed '/^$/d')

mkdir -p "$RESULTS_DIR/tests"

MANIFEST_JSON="$RESULTS_DIR/manifest.json"
INDEX_JSONL="$RESULTS_DIR/index.jsonl"
COMPLETED_LIST="$RESULTS_DIR/completed.list"

# Initialize manifest if creating fresh; else leave existing manifest
if [[ ! -f "$MANIFEST_JSON" ]]; then
  echo "[" > "$MANIFEST_JSON"
  first=1
  for nid in "${NODEIDS[@]}"; do
    # JSON escape minimal characters for nodeid
    esc_nid=${nid//"/\"}
    if [[ $first -eq 0 ]]; then echo "," >> "$MANIFEST_JSON"; fi
    printf '{"nodeid":"%s","tier":"%s","model":"%s"}' "$esc_nid" "$TIER" "${MODEL_ID:-mlx}" >> "$MANIFEST_JSON"
    first=0
  done
  echo "]" >> "$MANIFEST_JSON"
fi

# Prime completed set from prior index if resuming (keyed by nodeid|tier|model)
if [[ -f "$INDEX_JSONL" ]]; then
  # Regenerate completed.list
  : > "$COMPLETED_LIST"
  # Extract tuple keys with status passed
  awk -v OFS='|' -F'"' '
    /"status":"passed"/ {
      nid=""; tier=""; model="";
      for(i=1;i<=NF;i++){
        if($i=="nodeid"){nid=$(i+2)}
        if($i=="tier"){tier=$(i+2)}
        if($i=="model"){model=$(i+2)}
      }
      if(nid!="" && tier!="" && model!=""){print nid, tier, model}
    }
  ' "$INDEX_JSONL" >> "$COMPLETED_LIST" || true
fi

run_json() {
  local nodeid="$1" status="$2" started="$3" finished="$4" dur="$5" logdir="$6"
  local esc_nid=${nodeid//"/\"}
  printf '{"nodeid":"%s","status":"%s","started_at":"%s","finished_at":"%s","duration_sec":%s,"logdir":"%s","tier":"%s","model":"%s"}\n' \
    "$esc_nid" "$status" "$started" "$finished" "$dur" "$logdir" "$TIER" "${MODEL_ID:-mlx}"
}

should_run() {
  local nodeid="$1"
  local key="$nodeid|$TIER|${MODEL_ID:-mlx}"
  if [[ -f "$COMPLETED_LIST" ]] && grep -Fx -- "$key" "$COMPLETED_LIST" >/dev/null 2>&1; then
    if [[ "$FAILED_ONLY" == "1" ]]; then
      # Completed passed previously; skip in failed-only mode
      return 1
    fi
    # Already passed; skip in normal resume mode
    return 1
  fi
  # If failed-only requested, ensure the node had a prior non-passed record
  if [[ "$FAILED_ONLY" == "1" ]]; then
    if [[ -f "$INDEX_JSONL" ]] \
       && grep -F "\"nodeid\":\"$nodeid\"" "$INDEX_JSONL" \
            | grep -F "\"tier\":\"$TIER\"" \
            | grep -F "\"model\":\"${MODEL_ID:-mlx}\"" \
            | grep -qv '"status":"passed"'; then
      return 0
    else
      return 1
    fi
  fi
  return 0
}

overall_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)

for nid in "${NODEIDS[@]}"; do
  if [[ -n "$RESUME_ARG" ]]; then
    should_run "$nid" || { echo "[resume] skipping $nid"; continue; }
  fi

  # Safe folder name for this test
  safe_id=$(echo "$nid" | tr '/:\\[](),' '_______')
  tdir="$RESULTS_DIR/tests/$safe_id"
  # Variant subdirectory per tier/model to store side-by-side outputs
  model_label="${MODEL_ID:-mlx}"
  model_safe=$(echo "$model_label" | tr '/:\\[](), ' '_______')
  variant="${TIER}__${model_safe}"
  vdir="$tdir/$variant"
  mkdir -p "$vdir"

  # Write static testcase info (independent of variant)
  if [[ ! -f "$tdir/info.json" ]]; then
    esc_nid=${nid//"/\"}
    cat > "$tdir/info.json" <<INFOJSON
{
  "nodeid": "$esc_nid",
  "notes": "Static testcase metadata; scenario/agent fields may be populated by the field harness in future."
}
INFOJSON
  fi

  t_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  ts_epoch=$(date +%s)

  # Run single test node, direct evalforge output (if used) to per-test dir
  TEST_ENV=("EVALFORGE_OUTPUT=$vdir/evalforge" "EVALFORGE_FIELD_MODEL_TIER=$TIER")
  if [[ "$TIER" != "local" ]]; then
    TEST_ENV+=("OPENROUTER_API_KEY=$OPENROUTER_KEY" "OPENAI_API_KEY=$OPENROUTER_KEY" "OPENAI_BASE_URL=https://openrouter.ai/api/v1" "EVALFORGE_FIELD_MODEL=$MODEL_ID" "MODEL=$MODEL_ID")
  fi

  set +x
  echo "--- Running $nid ---"
  set -x
  # shellcheck disable=SC2068
  env ${TEST_ENV[@]} uv run pytest -q -- "$nid" --evalforge-output "$vdir/evalforge" >"$vdir/console.log" 2>&1 || true
  set +x

  exit_code=$?
  t_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  dur=$(($(date +%s)-ts_epoch))

  status="failed"
  if [[ $exit_code -eq 0 ]]; then status="passed"; fi

  # Ensure evalforge folder exists and seed placeholder files for easy review
  mkdir -p "$vdir/evalforge"
  : > "$vdir/evalforge/prompt.txt"
  : > "$vdir/evalforge/completion.txt"
  if [[ ! -s "$vdir/evalforge/prompt.txt" ]]; then echo "[placeholder] prompt not captured by adapter" > "$vdir/evalforge/prompt.txt"; fi
  if [[ ! -s "$vdir/evalforge/completion.txt" ]]; then echo "[placeholder] completion not captured by adapter" > "$vdir/evalforge/completion.txt"; fi

  # Persist per-test result JSON and append to index
  run_json "$nid" "$status" "$t_start" "$t_end" "$dur" "$vdir" > "$vdir/result.json"
  run_json "$nid" "$status" "$t_start" "$t_end" "$dur" "$vdir" >> "$INDEX_JSONL"
  if [[ "$status" == "passed" ]]; then echo "$nid|$TIER|${MODEL_ID:-mlx}" >> "$COMPLETED_LIST"; fi
done

overall_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Write top-level run.json and simple summary.json
total=${#NODEIDS[@]}
passed=$(awk -F'"' '/"status":"passed"/ {c++} END {print c+0}' "$INDEX_JSONL" 2>/dev/null || echo 0)
failed=$(awk -F'"' '/"status":"failed"/ {c++} END {print c+0}' "$INDEX_JSONL" 2>/dev/null || echo 0)

cat > "$RESULTS_DIR/run.json" <<RUNJSON
{
  "started_at": "$overall_start",
  "finished_at": "$overall_end",
  "tier": "$TIER",
  "model": "${MODEL_ID:-mlx}",
  "agents": "${AGENTS_CSV}",
  "notes": "${RUN_NOTES}",
  "total_collected": $total,
  "counts": {"passed": $passed, "failed": $failed}
}
RUNJSON

cat > "$RESULTS_DIR/summary.json" <<SUMMARY
{
  "tier": "$TIER",
  "model": "${MODEL_ID:-mlx}",
  "passed": $passed,
  "failed": $failed,
  "results_dir": "$RESULTS_DIR"
}
SUMMARY

set +x
echo "=== Field tests complete ==="
