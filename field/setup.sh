#!/usr/bin/env bash
# Clone field-test agents into field/agents/ at pinned commits.
#
# Usage:
#   bash field/setup.sh                                 # clone all from default agents.txt
#   bash field/setup.sh --file field/agents-stretch.txt   # clone from stretch list
#   bash field/setup.sh --file my-custom-agents.txt       # clone from custom list
#   bash field/setup.sh --agent slug1,slug2              # clone specific agents from default list
#   bash field/setup.sh --refresh                        # re-clone all (wipe and fresh clone)
#   bash field/setup.sh --dry-run                        # print what would be cloned
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENTS_DIR="$PROJECT_DIR/field/agents"

DRY_RUN=0
REFRESH=0
AGENTS_CSV=""
AGENT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) AGENTS_CSV="${2:-}"; shift 2;;
    --file) AGENT_FILE="${2:-}"; shift 2;;
    --refresh) REFRESH="1"; shift;;
    --dry-run) DRY_RUN="1"; shift;;
    -h|--help)
      echo "Usage: field/setup.sh [--file agents.txt] [--agent slug1,slug2] [--refresh] [--dry-run]"
      exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 1;;
  esac
done

# ── Read agent list from text file ──────────────────────────────────────
if [[ -z "$AGENT_FILE" ]]; then
  AGENT_FILE="$PROJECT_DIR/field/list1.txt"
fi

if [[ ! -f "$AGENT_FILE" ]]; then
  echo "Error: agent list file not found: $AGENT_FILE" >&2; exit 1
fi

echo "Agent list: $AGENT_FILE"

# Parse non-comment, non-empty lines
AGENTS=()
while IFS= read -r line; do
  line="${line%%#*}"           # strip comments
  line="${line#"${line%%[![:space:]]*}"}"  # trim leading whitespace
  [[ -z "$line" ]] && continue
  AGENTS+=("$line")
done < "$AGENT_FILE"

# ── Helpers ──────────────────────────────────────────────────────────────

clone_agent() {
  local slug="$1" repo="$2" sha="$3" adapter="$4" setup_cmd="$5"
  local target="$AGENTS_DIR/$slug"

  if [[ "$sha" == "TODO" ]]; then
    echo "[warn] $slug: commit SHA is TODO — cloning HEAD (not pinned)!"
    sha="HEAD"
  fi

  if [[ -d "$target/.git" ]]; then
    if [[ "$REFRESH" == "1" ]]; then
      echo "[refresh] removing $slug..."
      rm -rf "$target"
    else
      echo "[skip] $slug already cloned at $target"
      return 0
    fi
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[dry-run] would clone $repo → $target @ $sha"
    return 0
  fi

  echo "[clone] $repo → $target"
  git clone "$repo" "$target" --quiet 2>&1 || {
    echo "[error] clone failed for $slug ($repo)" >&2
    return 1
  }

  if [[ "$sha" != "HEAD" ]]; then
    git -C "$target" checkout "$sha" --quiet 2>&1 || {
      echo "[warn] $slug: checkout $sha failed, staying on HEAD" >&2
    }
  fi

  # Run setup command if provided and not empty
  if [[ -n "$setup_cmd" && "$setup_cmd" != "none" ]]; then
    echo "[setup] $slug: $setup_cmd"
    (cd "$target" && bash -c "$setup_cmd") || {
      echo "[warn] $slug: setup command failed (continuing)" >&2
    }
  fi

  echo "[ok] $slug cloned (adapter=$adapter)"
}

# ── Main ─────────────────────────────────────────────────────────────────

mkdir -p "$AGENTS_DIR"

echo "=== Field Agent Setup ==="
echo "Target: $AGENTS_DIR"
echo "Agents defined: ${#AGENTS[@]}"
echo ""

count=0
for entry in "${AGENTS[@]}"; do
  IFS='|' read -r slug repo sha adapter setup_cmd <<< "$entry"

  # Filter by --agent if specified
  if [[ -n "$AGENTS_CSV" ]]; then
    if ! echo "$AGENTS_CSV" | tr ',' '\n' | grep -qxF "$slug"; then
      continue
    fi
  fi

  clone_agent "$slug" "$repo" "$sha" "$adapter" "$setup_cmd" || true
  count=$((count + 1))
done

echo ""
echo "=== Complete: $count agent(s) processed ==="