#!/usr/bin/env bash
# Scan repo for secrets, credentials, and sensitive data.
# Uses trufflehog if available, falls back to basic pattern scanning.
# Usage: bash scripts/scan-secrets.sh
set -euo pipefail

echo "=== EvalForge Secrets Scan ==="

FOUND=0

if command -v trufflehog &>/dev/null; then
    echo "[trufflehog] scanning git history..."
    trufflehog git file://. --no-update --fail 2>/dev/null || FOUND=1
else
    echo "[basic] trufflehog not installed — running basic pattern scan..."

    # Check for common secret patterns in tracked files (not in .git or venv)
    PATTERNS=(
        'sk-[A-Za-z0-9_-]{32,}'           # OpenAI/OpenRouter keys
        'sk-ant-[A-Za-z0-9_-]{32,}'       # Anthropic keys
        'ghp_[A-Za-z0-9]{36}'             # GitHub PATs
        'gho_[A-Za-z0-9]{36}'             # GitHub OAuth
        'AIza[0-9A-Za-z_-]{35}'           # Google API keys
        'AKIA[0-9A-Z]{16}'                # AWS Access Keys
        'github_pat_[A-Za-z0-9_]{22,}'    # GitHub fine-grained tokens
    )

    for pattern in "${PATTERNS[@]}"; do
        matches=$(git ls-files | grep -v '.venv\|node_modules\|.git\|__pycache__\|.pytest_cache\|field/results' | xargs grep -lE "$pattern" 2>/dev/null || true)
        if [ -n "$matches" ]; then
            echo "[WARN] Pattern '$pattern' found in:"
            echo "$matches" | while read f; do echo "  $f"; done
            FOUND=1
        fi
    done
fi

# Check for common secret files
SECRET_FILES=(
    '.env'
    'credentials.json'
    'service-account.json'
    '*.pem'
    '*.key'
    'id_rsa*'
)

for pattern in "${SECRET_FILES[@]}"; do
    matches=$(git ls-files | grep "$pattern" | grep -v '.env.example' 2>/dev/null || true)
    if [ -n "$matches" ]; then
        echo "[WARN] Secret file '$pattern' tracked: $matches"
        FOUND=1
    fi
done

if [ "$FOUND" -eq 1 ]; then
    echo ""
    echo "[FAIL] Secrets or credential patterns found. Review the findings above."
    exit 1
fi

echo "[PASS] No secrets or credentials found."
