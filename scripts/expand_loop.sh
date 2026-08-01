#!/usr/bin/env bash
# ==============================================================================
# scripts/expand_loop.sh — the overnight roadmap loop (Git Bash / Windows).
# ==============================================================================
#
# Runs unattended: reads the LOOP:QUEUE fence in project-harness/ROADMAP.md, implements
# ONE task per fresh `claude -p` session, gates it, ticks it, commits it, and keeps going
# until the queue drains or something genuinely warrants a human.
#
# ------------------------------------------------------------------------------
# THE DESIGN INVARIANT
# ------------------------------------------------------------------------------
# Progress lives ONLY as ticked checkboxes in ROADMAP.md, and each task's commit
# contains its own tick. The commit IS the transaction. Kill this script at any instant
# — Ctrl-C, power cut, laptop lid — and there is nothing to reconcile: the next launch
# reads the roadmap, finds the first unticked task, and continues. There is no cursor
# file, no run-state JSON, no session id to resume. Do not add one.
#
# ------------------------------------------------------------------------------
# STATUS TOKENS (the skill's last line, bare, never in backticks — scar 6.9)
# ------------------------------------------------------------------------------
#   TASK_COMPLETE                 task done, gate green            -> next task
#   PHASE_COMPLETE                last task of the phase done      -> phase boundary
#   ALL_DONE                      queue drained                    -> finish
#   TASK_COMPLETE_BASELINE_RED    gate red, all failures pre-date  -> continue
#   TASK_COMMITTED_REGRESSION     new confirmed failure, committed -> continue, cap 3
#   HALT <reason>                 cannot proceed                   -> skip or halt
#
# ------------------------------------------------------------------------------
# THE SCARS — each is a lost night upstream. Do not remove these.
# ------------------------------------------------------------------------------
#  6.1  Never background the gate. A headless turn ends the moment it stops calling
#       tools; a session that backgrounds `make check` dies with work uncommitted.
#       Enforced in the SKILL prompt, in bold, three times. It is load-bearing.
#  6.2  Commit before you stop. Leftovers in the tree make the next run's clean-tree
#       preflight refuse, and the work is lost.
#  6.3  Usage-limit restart needs runaway guards. Four independent ones below.
#  6.4  A blocked prerequisite SKIPS the phase, it does not halt the night.
#  6.5  A red per-task gate must not lose the work: commit it, tick it UNVERIFIED,
#       flag it. Visible debt beats lost work.
#  6.6  A regression must not forfeit the rest of the phase. Cap, then halt.
#  6.7  The loop's own logs must never be tracked by git (.gitignore:1-2 covers this).
#  6.8  Report artifacts must be checkpointed, or the next task's clean-tree gate trips.
#  6.9  Status tokens must be bare on their own line.
#  6.10 Phase caps must count ROADMAP state, not tokens — a red-committed final task
#       suppresses PHASE_COMPLETE, so token-counting caps silently never trip.
#
# ------------------------------------------------------------------------------
# WINDOWS NOTES
# ------------------------------------------------------------------------------
# Everything platform-specific lives in scripts/loop_compat.sh. The critical one: a
# timed-out `claude` leaves its process tree ALIVE under Git Bash, so timeouts go
# through compat_run_timeout, which reaps via taskkill and VERIFIES the reap.
#
# Usage:
#   bash scripts/expand_loop.sh --max-tasks 1            # first bring-up, watch it
#   bash scripts/expand_loop.sh --max-phases 1
#   bash scripts/expand_loop.sh --start-at 20:00 --stop-at 08:00
#   bash scripts/expand_loop.sh --dry-run                # no model calls at all
# ==============================================================================

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "FATAL: not inside a git repository" >&2; exit 1; }
cd "$REPO_ROOT" || exit 1

# shellcheck source=scripts/loop_compat.sh
source "$REPO_ROOT/scripts/loop_compat.sh"
# shellcheck source=scripts/loop.config.sh
source "$REPO_ROOT/scripts/loop.config.sh"

# --- CLI defaults ---------------------------------------------------------------------
MAX_TASKS=0                 # 0 = unlimited
MAX_PHASES=0
START_AT=""
DRY_RUN=0
NO_SLEEP=0
COMMIT_DIRTY=0
FORCE_PHASE=""
# Unattended sessions cannot answer permission prompts. Overridable; see --permission-args.
CLAUDE_PERMISSION_ARGS="${CLAUDE_PERMISSION_ARGS:---dangerously-skip-permissions}"

LOCK_DIR="$LOOP_STATE_DIR/loop.lock"
STOP_AT="$MORNING_STOP_HOUR_LOCAL"

# --- run state (in memory only; the roadmap is the durable state) ----------------------
TASKS_DONE=0
PHASES_DONE=0
CONSECUTIVE_RED_GATES=0
CONSECUTIVE_RED_COMMITS=0
CONSECUTIVE_BLOCKED_PHASES=0
SKIPPED_PHASES=""
START_BRANCH=""
SESSION_LOG=""

usage() {
  sed -n '2,60p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --max-tasks)        MAX_TASKS="$2"; shift 2 ;;
    --max-phases)       MAX_PHASES="$2"; shift 2 ;;
    --start-at)         START_AT="$2"; shift 2 ;;
    --stop-at)          STOP_AT="$2"; shift 2 ;;
    --timeout-secs)     CLAUDE_TIMEOUT="$2"; shift 2 ;;
    --model)            MODEL="$2"; shift 2 ;;
    --review-model)     REVIEW_MODEL="$2"; shift 2 ;;
    --sleep-secs)       PHASE_SLEEP_SECS="$2"; shift 2 ;;
    --phase)            FORCE_PHASE="$2"; shift 2 ;;
    --permission-args)  CLAUDE_PERMISSION_ARGS="$2"; shift 2 ;;
    --max-red-gates)    MAX_CONSECUTIVE_RED_GATES="$2"; shift 2 ;;
    --max-red-commits)  MAX_RED_COMMITS="$2"; shift 2 ;;
    --with-services)    WITH_SERVICES=1; shift ;;
    --no-services)      WITH_SERVICES=0; shift ;;
    --no-autofix)       AUTOFIX_ENABLED=0; shift ;;
    --no-review)        SOFT_REVIEW_ENABLED=0; shift ;;
    --no-sleep)         NO_SLEEP=1; shift ;;
    --no-push)          PUSH_ENABLED=0; shift ;;
    --push)             PUSH_ENABLED=1; shift ;;
    --allow-main)       ALLOW_MAIN=1; shift ;;
    --commit-dirty)     COMMIT_DIRTY=1; shift ;;
    --dry-run)          DRY_RUN=1; shift ;;
    -h|--help)          usage ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

# ======================================================================================
# logging
# ======================================================================================
TIMESTAMP() { TZ="$RESTART_TZ" date '+%Y-%m-%d %H:%M:%S'; }
TODAY()     { TZ="$RESTART_TZ" date '+%Y-%m-%d'; }

log() {
  local line="[$(TIMESTAMP)] $*"
  if [ -n "$SESSION_LOG" ]; then echo "$line" | tee -a "$SESSION_LOG"; else echo "$line"; fi
}

fatal() { log "FATAL: $*"; exit 1; }

cursor() { $PY_RUN "$REPO_ROOT/scripts/roadmap_cursor.py" "$@"; }

# ======================================================================================
# preflight
# ======================================================================================
preflight() {
  compat_force_utf8
  export ROADMAP_FILE
  mkdir -p "$LOOP_LOG_DIR" "$LOOP_STATE_DIR"
  SESSION_LOG="$LOOP_LOG_DIR/loop-$(TZ="$RESTART_TZ" date '+%Y%m%d-%H%M%S').log"
  : > "$SESSION_LOG"

  compat_lock_acquire "$LOCK_DIR" || fatal "another loop holds $LOCK_DIR"
  trap 'compat_lock_release "$LOCK_DIR"' EXIT INT TERM

  command -v claude >/dev/null 2>&1 || fatal "claude CLI not on PATH"
  command -v make   >/dev/null 2>&1 || fatal "make not on PATH"

  START_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  [ "$START_BRANCH" != "HEAD" ] || fatal "detached HEAD — check out a branch first"
  if [ "$START_BRANCH" = "$DEFAULT_BRANCH" ] && [ "$ALLOW_MAIN" != "1" ]; then
    fatal "refusing to run on '$DEFAULT_BRANCH' (use --allow-main to override)"
  fi

  # Scar 6.2 / 6.7: a dirty tree means the previous run lost work, or the user has
  # edits the loop would sweep into a task commit. Refuse, or checkpoint deliberately.
  if [ -n "$(git status --porcelain)" ]; then
    if [ "$COMMIT_DIRTY" = "1" ]; then
      git add -A && git commit -q -m "chore(loop): checkpoint dirty tree before run" \
        || fatal "startup checkpoint commit failed — halting cleanly, nothing lost"
      log "preflight: committed a dirty tree (--commit-dirty)"
    else
      fatal "working tree not clean (use --commit-dirty to checkpoint it first)"
    fi
  fi

  cursor --verify >/dev/null || fatal "roadmap failed --verify; fix the grammar first"

  if [ "$WITH_SERVICES" = "1" ]; then
    if compat_services_up "$SERVICES_HEALTH_TIMEOUT"; then
      log "preflight: services healthy — integration tests will RUN this night"
    else
      # Never red: an unreachable daemon is infrastructure, not a code regression.
      log "preflight: services unavailable — integration tests will SKIP (degraded, not red)"
    fi
  fi
  compat_ollama_ready && log "preflight: ollama reachable" || log "preflight: ollama not reachable (fine unless a live task runs)"

  log "preflight OK | branch=$START_BRANCH model=$MODEL push=$PUSH_ENABLED services=$WITH_SERVICES"
  log "queue: $(cursor --status | tail -1)"
}

# ======================================================================================
# clocks
# ======================================================================================
wait_until_start() {
  [ -n "$START_AT" ] || return 0
  local now target
  now="$(TZ="$RESTART_TZ" date +%s)"
  target="$(TZ="$RESTART_TZ" date -d "today $START_AT" +%s 2>/dev/null)" || return 0
  [ "$target" -le "$now" ] && target="$(TZ="$RESTART_TZ" date -d "tomorrow $START_AT" +%s)"
  local delta=$((target - now))
  log "sleeping ${delta}s until $START_AT before starting work"
  sleep "$delta"
}

past_morning_stop() {
  # Stops STARTING new work between the stop hour and noon; never interrupts running work.
  local now stop
  now="$(TZ="$RESTART_TZ" date +%H%M%S)"; now="${now#"${now%%[!0]*}"}"; now="${now:-0}"
  stop="$(echo "$STOP_AT" | tr -d ':')"; stop="${stop#"${stop%%[!0]*}"}"; stop="${stop:-0}"
  [ "$now" -ge "$stop" ] && [ "$now" -lt 120000 ]
}

# ======================================================================================
# reports (scar 6.8 — uncommitted reports trip the NEXT task's clean-tree gate)
# ======================================================================================
flag_for_human() {
  local title="$1" detail="$2"
  mkdir -p "$(dirname "$HUMAN_VERIFICATION_FILE")"
  {
    echo ""
    echo "## $(TIMESTAMP) — $title"
    echo ""
    echo "$detail"
  } >> "$HUMAN_VERIFICATION_FILE"
  log "FLAGGED FOR HUMAN: $title"
}

checkpoint_reports() {
  # Only stage report files that actually exist: `git add` fails as a whole on a missing
  # pathspec, which silently left the reports uncommitted and tripped the NEXT task's
  # clean-tree preflight — exactly the failure scar 6.8 describes.
  local files=() f changed
  for f in "$HUMAN_VERIFICATION_FILE" "$SOFT_REVIEW_FILE" "$HARNESS_DIR/ROADMAP.md"; do
    [ -e "$f" ] && files+=("$f")
  done
  [ "${#files[@]}" -gt 0 ] || return 0
  changed="$(git status --porcelain -- "${files[@]}" 2>/dev/null)"
  [ -n "$changed" ] || return 0
  git add -- "${files[@]}" >/dev/null 2>&1 || true
  git commit -q -m "chore(loop): checkpoint night-shift reports" >/dev/null 2>&1 || true
  log "checkpointed report artifacts"
}

# ======================================================================================
# claude sessions
# ======================================================================================
run_claude_session() {
  # Usage: run_claude_session <logfile> <timeout> <model> <prompt>
  local logfile="$1" timeout="$2" model="$3" prompt="$4" rc=0
  if [ "$DRY_RUN" = "1" ]; then
    echo "DRY-RUN: would run claude with prompt: $prompt" > "$logfile"
    echo "AUTO_STATUS: DRY_RUN" >> "$logfile"
    return 0
  fi
  # shellcheck disable=SC2086
  compat_run_timeout "$timeout" "$logfile" \
    claude -p "$prompt" --model "$model" $CLAUDE_PERMISSION_ARGS
  rc=$?
  [ "$rc" -eq 124 ] && log "session TIMED OUT after ${timeout}s (tree reaped)"
  return "$rc"
}

read_status_token() {
  # Scar 6.9: the token must be BARE on its own line. Backticked tokens are ignored
  # here deliberately, so a malformed skill surfaces as "no token" rather than silently
  # reading as a halt.
  grep -aoE '^AUTO_STATUS: [A-Z_]+( .*)?$' "$1" 2>/dev/null | tail -1 | sed 's/^AUTO_STATUS: //'
}

looks_like_usage_limit() {
  grep -qaiE 'usage limit reached|approaching your usage limit|resets at|rate.?limit exceeded' "$1" 2>/dev/null
}

# ======================================================================================
# usage-limit auto-restart, with the four runaway guards (scar 6.3)
# ======================================================================================
usage_restart_should_halt() {
  local now done_count last_ts last_done stashes
  now="$(date +%s)"
  done_count="$(cursor --status | tail -1 | sed 's/.*done=\([0-9]*\).*/\1/')"
  LOOP_RESTART_COUNT="${LOOP_RESTART_COUNT:-0}"

  # Guard 1 — cap per exec lineage.
  [ "$LOOP_RESTART_COUNT" -ge "$MAX_USAGE_RESTARTS" ] && {
    log "usage-restart guard: hit cap $MAX_USAGE_RESTARTS"; return 0; }

  # Guard 2 — rapid repeat: two hits closer than the floor is a bug, not real quota.
  last_ts="$(cat "$LOOP_STATE_DIR/last_usage_ts" 2>/dev/null || echo 0)"
  if [ "$last_ts" -gt 0 ] && [ $((now - last_ts)) -lt "$MIN_SECS_BETWEEN_RESTARTS" ]; then
    log "usage-restart guard: repeat after $((now - last_ts))s"; return 0
  fi

  # Guard 3 — no progress between two consecutive hits.
  last_done="$(cat "$LOOP_STATE_DIR/last_usage_done" 2>/dev/null || echo -1)"
  if [ "$last_done" = "$done_count" ]; then
    log "usage-restart guard: no roadmap progress since the last restart"; return 0
  fi

  # Guard 4 — stash pile-up means restarts are not recovering.
  stashes="$(git stash list 2>/dev/null | grep -c 'loop-auto-restart' || echo 0)"
  if [ "$stashes" -ge "$MAX_LOOP_STASHES" ]; then
    log "usage-restart guard: $stashes unresolved auto-restart stashes"; return 0
  fi

  echo "$now" > "$LOOP_STATE_DIR/last_usage_ts"
  echo "$done_count" > "$LOOP_STATE_DIR/last_usage_done"
  return 1
}

restart_after_usage_reset() {
  if usage_restart_should_halt; then
    flag_for_human "usage-limit restart suppressed" "A guard tripped; see the run log."
    return 1
  fi
  if [ -n "$(git status --porcelain)" ]; then
    git stash push -u -m "loop-auto-restart $(TIMESTAMP)" >/dev/null 2>&1 || true
    log "stashed uncommitted work before the usage-reset sleep"
  fi
  log "usage limit hit — sleeping ${USAGE_RESET_SLEEP_SECS}s, then re-exec"
  sleep "$USAGE_RESET_SLEEP_SECS"
  compat_lock_release "$LOCK_DIR"
  export LOOP_RESTART_COUNT=$(( ${LOOP_RESTART_COUNT:-0} + 1 ))
  exec bash "$REPO_ROOT/scripts/expand_loop.sh" "${ORIGINAL_ARGV[@]}"
}

# ======================================================================================
# gate + repair
# ======================================================================================
run_full_gate() {
  local logfile="$1"
  log "running gate: $GATE_CHECK_CMD"
  ( eval "$GATE_CHECK_CMD" ) > "$logfile" 2>&1
  return $?
}

try_autofix() {
  # One bounded repair session for an AUTOFIX-class red gate. Its diff is scanned for
  # gaming, the full gate is re-run, and the repair is committed SEPARATELY and flagged.
  local failed_check="$1" fixlog="$LOOP_LOG_DIR/autofix-$(date +%s).log"
  local before; before="$(git rev-parse HEAD)"

  log "autofix: attempting bounded repair of '$failed_check'"
  run_claude_session "$fixlog" "$FIX_TIMEOUT" "$FIX_MODEL" \
    "/fix-make-failure --auto --check $failed_check"

  if [ -z "$(git status --porcelain)" ] && [ "$before" = "$(git rev-parse HEAD)" ]; then
    log "autofix: session changed nothing"; return 1
  fi

  if ! $PY_RUN "$REPO_ROOT/scripts/scan_fix_diff.py" > "$fixlog.scan" 2>&1; then
    log "autofix: REJECTED — gate-gaming detected"
    cat "$fixlog.scan" | while read -r l; do log "  $l"; done
    git checkout -- . 2>/dev/null; git clean -fd 2>/dev/null
    flag_for_human "autofix rejected (gate-gaming)" "$(cat "$fixlog.scan")"
    return 1
  fi

  if ! run_full_gate "$fixlog.gate"; then
    log "autofix: repair did not turn the gate green — reverting the repair only"
    git checkout -- . 2>/dev/null; git clean -fd 2>/dev/null
    return 1
  fi

  git add -A && git commit -q -m "fix(loop): auto-repair $failed_check [needs review]"
  flag_for_human "auto-repair committed" \
    "Check '$failed_check' was repaired unattended at $(git rev-parse --short HEAD). Review the diff."
  log "autofix: repair committed and flagged"
  return 0
}

run_phase_gate() {
  local phase="$1" gatelog="$LOOP_LOG_DIR/gate-$phase-$(date +%s).log" rc=0 cls=0

  if run_full_gate "$gatelog"; then
    log "phase gate GREEN for $phase"
    CONSECUTIVE_RED_GATES=0
    return 0
  fi

  log "phase gate RED for $phase — classifying"
  $PY_RUN "$REPO_ROOT/scripts/classify_gate_failure.py" > "$gatelog.class" 2>&1
  cls=$?
  local verdict; verdict="$(grep -aoE 'CLASSIFICATION=[A-Z]+' "$gatelog.class" | head -1)"
  local failed;  failed="$(grep -aoE 'FAILED_CHECK=[^ ]+' "$gatelog.class" | head -1 | cut -d= -f2)"
  log "gate classification: ${verdict:-unknown} (${failed:-unknown})"

  if [ "$cls" -eq 0 ] && [ "$AUTOFIX_ENABLED" = "1" ]; then
    if try_autofix "$failed"; then CONSECUTIVE_RED_GATES=0; return 0; fi
  fi

  # Tolerance: a still-red gate does NOT halt. It is logged and the phase's commits
  # stand. Only MAX_CONSECUTIVE_RED_GATES in a row halts.
  CONSECUTIVE_RED_GATES=$((CONSECUTIVE_RED_GATES + 1))
  flag_for_human "phase gate red after $phase" \
    "$(tail -40 "$gatelog.class" 2>/dev/null; echo; tail -40 "$gatelog")"
  if [ "$CONSECUTIVE_RED_GATES" -ge "$MAX_CONSECUTIVE_RED_GATES" ]; then
    log "HALT: $CONSECUTIVE_RED_GATES consecutive red phase gates"
    return 2
  fi
  return 1
}

# ======================================================================================
# phase boundary — deterministic bash, no LLM. Never spend a model call on something
# `make` can answer.
# ======================================================================================
run_soft_review() {
  local phase="$1" reviewlog="$LOOP_LOG_DIR/review-$phase-$(date +%s).log"
  [ "$SOFT_REVIEW_ENABLED" = "1" ] || return 0
  [ "$DRY_RUN" = "1" ] && return 0
  log "soft review of phase $phase (model=$REVIEW_MODEL)"
  run_claude_session "$reviewlog" "$REVIEW_SESSION_TIMEOUT" "$REVIEW_MODEL" \
"Review ONLY the diff of the commits made for roadmap phase $phase on this branch.
Run: git log --oneline -20 and git diff HEAD~\$(git rev-list --count HEAD ^origin/HEAD 2>/dev/null || echo 1)..HEAD
Report at most 5 concrete findings (correctness, missed edge cases, project-rule
violations from project-harness/CLAUDE.md). Be terse. Do NOT edit any file."
  {
    echo ""; echo "## $(TIMESTAMP) — phase $phase"; echo ""
    tail -60 "$reviewlog"
  } >> "$SOFT_REVIEW_FILE"
}

seed_gate_baseline() {
  # Written at phase boundaries ONLY. Re-seeding mid-phase would let a task launder its
  # own regression into "pre-existing".
  log "re-seeding the failing-test baseline for the next phase"
  $PY_RUN "$REPO_ROOT/scripts/gate_baseline.py" --write --note "after-phase-${1:-init}" \
    2>&1 | while read -r l; do log "  $l"; done
}

push_branch() {
  [ "$PUSH_ENABLED" = "1" ] || { log "push disabled — staying local"; return 0; }
  git push origin "$START_BRANCH" 2>&1 | while read -r l; do log "  push: $l"; done
}

run_phase_boundary() {
  local phase="$1" rc=0
  log "=== phase boundary: $phase ==="
  checkpoint_reports
  run_phase_gate "$phase"; rc=$?
  [ "$rc" -eq 2 ] && return 2
  run_soft_review "$phase"
  checkpoint_reports
  push_branch
  seed_gate_baseline "$phase"
  PHASES_DONE=$((PHASES_DONE + 1))
  if [ "$NO_SLEEP" != "1" ] && [ "$PHASE_SLEEP_SECS" -gt 0 ]; then
    log "sleeping ${PHASE_SLEEP_SECS}s to let usage headroom regenerate"
    sleep "$PHASE_SLEEP_SECS"
  fi
  return 0
}

# ======================================================================================
# per-task handling
# ======================================================================================
skip_phase() {
  local phase="$1" reason="$2"
  SKIPPED_PHASES="${SKIPPED_PHASES:+$SKIPPED_PHASES,}$phase"
  CONSECUTIVE_BLOCKED_PHASES=$((CONSECUTIVE_BLOCKED_PHASES + 1))
  flag_for_human "phase $phase skipped" "$reason"
  log "skipping phase $phase ($reason); blocked-run=$CONSECUTIVE_BLOCKED_PHASES"
  if [ "$CONSECUTIVE_BLOCKED_PHASES" -ge "$MAX_CONSECUTIVE_BLOCKED_PHASES" ]; then
    log "HALT: $CONSECUTIVE_BLOCKED_PHASES consecutive blocked phases with no progress"
    return 2
  fi
  return 0
}

phase_now_complete() {
  # Scar 6.10: ask the ROADMAP, never count tokens.
  cursor --phase-done "$1" >/dev/null 2>&1
}

handle_task_result() {
  local phase="$1" task="$2" token="$3" tasklog="$4"

  case "$token" in
    TASK_COMPLETE|TASK_COMPLETE_BASELINE_RED|DRY_RUN)
      TASKS_DONE=$((TASKS_DONE + 1))
      CONSECUTIVE_RED_COMMITS=0
      CONSECUTIVE_BLOCKED_PHASES=0
      [ "$token" = "TASK_COMPLETE_BASELINE_RED" ] && \
        flag_for_human "task $task committed with a pre-existing red gate" \
          "Every failure pre-dated this task (baseline attribution). Nothing new broke."
      return 0 ;;

    PHASE_COMPLETE)
      TASKS_DONE=$((TASKS_DONE + 1))
      CONSECUTIVE_RED_COMMITS=0
      CONSECUTIVE_BLOCKED_PHASES=0
      return 10 ;;   # caller runs the phase boundary

    TASK_COMMITTED_REGRESSION)
      # Scar 6.6: do NOT forfeit the phase over one regression.
      TASKS_DONE=$((TASKS_DONE + 1))
      CONSECUTIVE_RED_COMMITS=$((CONSECUTIVE_RED_COMMITS + 1))
      flag_for_human "task $task introduced a confirmed regression" \
        "Committed anyway as visible debt (scar 6.5). Run $CONSECUTIVE_RED_COMMITS of $MAX_RED_COMMITS."
      if [ "$CONSECUTIVE_RED_COMMITS" -ge "$MAX_RED_COMMITS" ]; then
        log "HALT: $CONSECUTIVE_RED_COMMITS consecutive regressions"
        return 2
      fi
      return 0 ;;

    ALL_DONE) return 1 ;;

    HALT*)
      local reason="${token#HALT }"
      case "$reason" in
        blocked-prerequisite*|ask-gate*|needs-decision*|live-task*)
          skip_phase "$phase" "$reason"; return $? ;;
        *)
          flag_for_human "HALT on task $task" "$reason"
          log "HALT: $reason"
          return 2 ;;
      esac ;;

    "")
      if looks_like_usage_limit "$tasklog"; then
        restart_after_usage_reset || return 2
        return 0
      fi
      flag_for_human "no status token from task $task" \
        "The session ended without a bare AUTO_STATUS line. Log: $tasklog"
      log "HALT: no status token (see $tasklog)"
      return 2 ;;

    *)
      flag_for_human "unknown status token from task $task" "token=$token"
      log "HALT: unrecognised token '$token'"
      return 2 ;;
  esac
}

run_one_task() {
  local phase="$1" task="$2"
  local tasklog="$LOOP_LOG_DIR/task-$task-$(date +%s).log"
  local rc token

  log "--- task $task (phase $phase) -> $tasklog"
  run_claude_session "$tasklog" "$CLAUDE_TIMEOUT" "$MODEL" \
    "/expand-linear-next --auto --single-task --phase $phase --task $task"
  rc=$?

  if [ "$rc" -eq 124 ]; then
    flag_for_human "task $task timed out" "Killed after ${CLAUDE_TIMEOUT}s; tree reaped."
    # Scar 6.2: anything left in the tree would trip the next task's preflight.
    if [ -n "$(git status --porcelain)" ]; then
      git stash push -u -m "loop-timeout $task $(TIMESTAMP)" >/dev/null 2>&1 || true
      log "stashed the timed-out task's partial work"
    fi
    return 2
  fi

  token="$(read_status_token "$tasklog")"
  log "status token: '${token:-<none>}'"
  handle_task_result "$phase" "$task" "$token" "$tasklog"
}

# ======================================================================================
# main
# ======================================================================================
ORIGINAL_ARGV=("$@")

main() {
  preflight
  wait_until_start

  [ "$(cursor --status | tail -1)" ] && log "starting: $(cursor --status | tail -1)"
  seed_gate_baseline "init"

  local next phase task rc
  while :; do
    if past_morning_stop; then
      log "past morning stop ($STOP_AT) — not starting new work"; break
    fi
    if [ "$MAX_TASKS" -gt 0 ] && [ "$TASKS_DONE" -ge "$MAX_TASKS" ]; then
      log "reached --max-tasks $MAX_TASKS"; break
    fi
    if [ "$MAX_PHASES" -gt 0 ] && [ "$PHASES_DONE" -ge "$MAX_PHASES" ]; then
      log "reached --max-phases $MAX_PHASES"; break
    fi

    if [ -n "$FORCE_PHASE" ]; then
      next="$(cursor --next-after "$FORCE_PHASE" --exclude "$SKIPPED_PHASES")"
    else
      next="$(cursor --next --exclude "$SKIPPED_PHASES")"
    fi

    if [ "$next" = "ALL_DONE" ] || [ -z "$next" ]; then
      log "ALL_DONE — no actionable tasks remain inside the queue fence"; break
    fi

    phase="$(echo "$next" | sed -n 's/.*PHASE=\([^ ]*\).*/\1/p')"
    task="$(echo "$next"  | sed -n 's/.*TASK=\([^ ]*\).*/\1/p')"
    [ -n "$phase" ] && [ -n "$task" ] || fatal "could not parse cursor output: $next"

    run_one_task "$phase" "$task"; rc=$?

    # `boundary_ran` is tracked separately because run_phase_boundary reassigns rc —
    # reusing rc as the guard fired the boundary a SECOND time for every phase.
    local boundary_ran=0 brc=0
    case "$rc" in
      0) ;;                                   # continue
      1) log "queue drained"; break ;;
      2) log "stopping: halt condition"; break ;;
      10)
        run_phase_boundary "$phase"; brc=$?
        boundary_ran=1
        [ "$brc" -eq 2 ] && { log "stopping: repeated red gates"; break; }
        ;;
    esac

    # Scar 6.10: even without a PHASE_COMPLETE token, ask the ROADMAP. A red-committed
    # final task suppresses the token, so a token-only check silently never fires.
    if [ "$boundary_ran" -eq 0 ] && phase_now_complete "$phase"; then
      run_phase_boundary "$phase" || true
    fi

    if [ "$NO_SLEEP" != "1" ] && [ "$TASK_SLEEP_SECS" -gt 0 ]; then
      sleep "$TASK_SLEEP_SECS"
    fi
  done

  checkpoint_reports
  log "=== run finished | tasks=$TASKS_DONE phases=$PHASES_DONE skipped=[${SKIPPED_PHASES:-none}] ==="
  log "queue now: $(cursor --status | tail -1)"
  [ -s "$HUMAN_VERIFICATION_FILE" ] && log "REVIEW: $HUMAN_VERIFICATION_FILE"
  return 0
}

main
