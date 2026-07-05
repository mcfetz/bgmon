#!/bin/bash
# bgmon check script - runs ruff, ty, and compileall, then triggers ntfy
# Usage: ./scripts/check.sh [backend|frontend]
set -uo pipefail

TARGET="${1:-backend}"
cd "/home/daniel/development/bgmon/$TARGET" || { echo "FAIL: cd $TARGET"; exit 1; }

source .venv/bin/activate 2>/dev/null || true

RUFF_RESULT=""
TY_RESULT=""
COMPILE_RESULT=""

echo "=== RUFF ($TARGET) ==="
RUFF_OUTPUT=$(ruff check . 2>&1 || true)
RUFF_EXIT=$?
RUFF_LINES=$(echo "$RUFF_OUTPUT" | tail -1)
RUFF_RESULT="exit=$RUFF_EXIT, $RUFF_LINES"

echo "=== TY ($TARGET) ==="
TY_OUTPUT=$(ty check . 2>&1 || true)
TY_EXIT=$?
TY_ERRORS=$(echo "$TY_OUTPUT" | grep -c "^error" || echo 0)
TY_RESULT="exit=$TY_EXIT, errors=$TY_ERRORS"

echo "=== COMPILEALL ($TARGET) ==="
COMPILE_OUTPUT=$(python -m compileall -q . 2>&1 || true)
COMPILE_EXIT=$?
COMPILE_RESULT="exit=$COMPILE_EXIT"

# Determine overall status
TOTAL_ERRORS=$((RUFF_EXIT + TY_ERRORS + COMPILE_EXIT))
STATUS="OK"
if [ "$TOTAL_ERRORS" -gt 0 ]; then
    STATUS="ISSUES"
fi

# Trigger ntfy
if [ -n "${NTFY_TOPIC:-}" ]; then
    MSG="$TARGET checks: ruff=$RUFF_RESULT | ty=$TY_RESULT | compile=$COMPILE_RESULT"
    curl -sf \
        -H "Title: bgmon $TARGET checks: $STATUS" \
        -H "Priority: low" \
        -H "Tags: bgmon,check,ci" \
        -d "$MSG" \
        "https://ntfy.familie-heise.de/$NTFY_TOPIC" >/dev/null 2>&1 || true
fi

echo ""
echo "=== SUMMARY ==="
echo "ruff:   $RUFF_RESULT"
echo "ty:     $TY_RESULT"
echo "compile: $COMPILE_RESULT"
echo "status: $STATUS"

[ "$TOTAL_ERRORS" -eq 0 ] || exit 1
