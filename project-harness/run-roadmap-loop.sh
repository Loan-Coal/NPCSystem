#!/usr/bin/env bash
# Drives /expand-next across every unchecked ROADMAP phase, one fresh `claude -p`
# session per phase, until the roadmap is done or a phase halts for your input.
# State persists on disk (ROADMAP [x] checkboxes), never in conversation context.
#
# Usage:  bash project-harness/run-roadmap-loop.sh
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

PROMPT_FILE="project-harness/.loop-prompt.txt"   # the per-iteration prompt
MAX_ITERS=12                                       # safety cap: 6 phases + margin
LOG_DIR="project-harness/.loop-logs"
mkdir -p "$LOG_DIR"

# Refuse to run on a dirty tree or detached HEAD — every phase commits.
[ -z "$(git status --porcelain)" ] || { echo "ABORT: working tree not clean"; exit 1; }
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" != "HEAD" ] || { echo "ABORT: detached HEAD"; exit 1; }
echo "Looping /expand-next on branch '$branch' (max $MAX_ITERS iterations)"

for ((i=1; i<=MAX_ITERS; i++)); do
  ts="$(date +%Y%m%d-%H%M%S)"; log="$LOG_DIR/iter-$i-$ts.log"
  before="$(git rev-parse HEAD)"
  echo "=== iteration $i ($ts) -> $log ==="

  claude -p "$(cat "$PROMPT_FILE")" --dangerously-skip-permissions 2>&1 | tee "$log"

  after="$(git rev-parse HEAD)"
  tail="$(grep -Eo 'LOOP_(DONE|CONTINUE|HALT.*)' "$log" | tail -1)"

  case "$tail" in
    LOOP_DONE)     echo "DONE: roadmap has no unchecked phases."; exit 0 ;;
    LOOP_HALT*)    echo "HALT: ${tail#LOOP_HALT: } - stopping for you."; exit 2 ;;
    LOOP_CONTINUE)
      [ "$before" != "$after" ] || { echo "STUCK: CONTINUE but no new commit. Stopping."; exit 3; }
      echo "phase done @ $after; next fresh session..." ;;
    *) echo "STUCK: no control token emitted. Stopping. See $log."; exit 4 ;;
  esac
done
echo "Hit MAX_ITERS=$MAX_ITERS without DONE. Stopping - inspect and resume."; exit 5
