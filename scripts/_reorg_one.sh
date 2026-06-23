#!/usr/bin/env bash
# TEMPORARY: delete by end of task REORG-PR6. Reason: guarded per-domain wrapper
# (move + collect-only smoke + commit only if collection stays clean at 2579).
set -euo pipefail
DOMAIN="$1"; PURPOSE="$2"; shift 2
bash scripts/_reorg_move_domain.sh "$DOMAIN" "$PURPOSE" "$@"
OUT=$(python -m pytest tests/ --collect-only -q 2>&1 | grep -E "tests collected|errors during collection" || true)
echo "$OUT"
if echo "$OUT" | grep -q "2579 tests collected"; then
  git add -A
  git commit -q -m "refactor(graph): move $DOMAIN/ into domain sub-package (PR-6)"
  echo "OK committed $DOMAIN"
else
  echo "SMOKE FAILED for $DOMAIN — not committed"; exit 1
fi
