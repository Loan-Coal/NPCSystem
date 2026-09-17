#!/usr/bin/env bash
# eval_stack_at.sh — rebuild the ISOLATED eval stack from a commit and prove it is running it.
#
# The app image is not bind-mounted: a stack that is merely "up" runs whatever commit it was
# built from, so a live check against it checks old code. Every live check in the overnight
# loop therefore rebuilds first, through this script (.claude/commands/expand-linear-next.md,
# "Live checks"). It only ever touches compose project `npcsystem-eval` (app :8001,
# neo4j :7688, volume neo4j_eval_data) — never the default dev stack or its database.
#
# Usage:
#   bash scripts/eval_stack_at.sh                 # rebuild from the working tree (HEAD + edits)
#   bash scripts/eval_stack_at.sh <commit>        # rebuild from an older commit (git archive)
#   bash scripts/eval_stack_at.sh <ref> --reset   # drop the eval Neo4j volume first
#
# Exit 0 and prints EVAL_STACK_SHA=<sha> only when /health reports the requested sha.
set -euo pipefail

ref="${1:-HEAD}"
reset="${2:-}"
repo="$(git rev-parse --show-toplevel)"
cd "$repo"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) py="$repo/.venv/Scripts/python.exe" ;;
  *)                    py="$repo/.venv/bin/python" ;;
esac

[ -f .env ] || { echo "eval_stack_at: .env missing in $repo" >&2; exit 2; }
sha="$(git rev-parse --short "$ref")"
head_sha="$(git rev-parse --short HEAD)"
compose_files=(-f docker-compose.yml -f docker-compose.freeze.yml -f docker-compose.eval.yml)

if [ "$reset" = "--reset" ]; then
  docker compose -p npcsystem-eval "${compose_files[@]}" down -v
fi

if [ "$sha" = "$head_sha" ]; then
  # Build context is the working tree, so uncommitted task edits are included.
  BUILD_SHA="$sha" docker compose -p npcsystem-eval "${compose_files[@]}" up -d --build
else
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  git archive "$sha" | tar -x -C "$tmp"
  cp .env "$tmp/.env"
  (cd "$tmp" && BUILD_SHA="$sha" docker compose -p npcsystem-eval "${compose_files[@]}" up -d --build)
fi

"$py" e2e/scripts/boot_check.py --base-url http://localhost:8001 --expect-sha "$sha"
echo "EVAL_STACK_SHA=$sha"
