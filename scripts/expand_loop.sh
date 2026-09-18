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
#   bash scripts/expand_loop.sh --stop-at none           # run the queue out, any hour
#   bash scripts/expand_loop.sh --dry-run                # no model calls at all
#
# Stale lock: a killed run can leave the lock dir behind. A dead holder is reclaimed
# automatically; a holder pid that is still alive (a reused MSYS pid) is not, and the run
# aborts with "FATAL: another loop holds ...". Confirm no loop is running, then:
#   rm -rf project-harness/.loop-state/loop.lock
#
# --stop-at resolves ONCE at startup to the next occurrence of that time, so a run
# started at 09:00 stops at 08:00 TOMORROW, and one started at 06:00 stops at 08:00
# today. It only stops new work from STARTING; a running task is never interrupted.
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
# Deliberately NEVER reset on success: a counter that resets measures a streak, not a
# run, and alternating good/bad tasks were unbounded under MAX_RED_COMMITS. Per-run total.
CONSECUTIVE_RED_COMMITS=0
CONSECUTIVE_BLOCKED_PHASES=0
# ISSUE-126 guard: the cursor is the only progress signal, and the session (not this
# driver) advances it. Track the last dispatched task id so a cursor that never moves
# halts the run instead of re-running the same task all night.
LAST_TASK_ID=""
SAME_TASK_REPEATS=0
MAX_SAME_TASK_REPEATS="${MAX_SAME_TASK_REPEATS:-2}"
SKIPPED_PHASES=""
START_BRANCH=""
SESSION_LOG=""
# Absolute epoch instant, resolved once in main(). Empty = the stop guard is disabled.
STOP_EPOCH=""

usage() {
  # Prints the header block: every comment line after the shebang, stopping at the first
  # line that is not a comment. A hardcoded range silently truncated whenever the header
  # grew, which is how the --stop-at docs went missing from --help.
  awk 'NR == 1 { next } !/^#/ { exit } { sub(/^# ?/, ""); print }' "$0"
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
# Plain `date`, no TZ prefix: Git Bash ships no tzdata, so TZ=<any name> silently
# returns UTC (measured — TZ=Foo/Bar behaves identically to TZ=Europe/Paris). The bare
# system clock is the only one that reads correct local time here.
TIMESTAMP() { date '+%Y-%m-%d %H:%M:%S'; }
TODAY()     { date '+%Y-%m-%d'; }

log() {
  local line="[$(TIMESTAMP)] $*"
  if [ -n "$SESSION_LOG" ]; then echo "$line" | tee -a "$SESSION_LOG"; else echo "$line"; fi
}

fatal() { log "FATAL: $*"; exit 1; }

cursor() { $PY_RUN "$REPO_ROOT/scripts/roadmap_cursor.py" "$@"; }
clock()  { $PY_RUN "$REPO_ROOT/scripts/loop_clock.py"     "$@"; }
gates()  { $PY_RUN "$REPO_ROOT/scripts/check_human_gates.py" "$@"; }

# ======================================================================================
# preflight
# ======================================================================================
preflight_worktree() {
  # ISSUE-139 / T0.1. Sessions commit with `git add -A`, so in a shared checkout a concurrent
  # interactive edit lands in a commit nobody gated. A worktree makes that impossible.
  local git_dir common_dir
  git_dir="$(cd "$(git rev-parse --git-dir)" && pwd -P)"
  common_dir="$(cd "$(git rev-parse --git-common-dir)" && pwd -P)"
  if [ "$git_dir" = "$common_dir" ]; then
    fatal "refusing to run in the primary checkout — interactive edits here get swept into
  the loop's commits (ISSUE-139). Run it from a dedicated worktree:
    git worktree add ../NPCSystem-loop -b auto/roadmap-night
  then provision it and start the loop there — see project-harness/OVERNIGHT_LOOP.md § Quick start."
  fi

  # A fresh worktree has no .venv/.env (gitignored); every gate would die on a missing tool.
  # Do NOT link the primary .venv: its editable install imports the PRIMARY checkout's src/.
  local py=""
  [ -x "$REPO_ROOT/.venv/Scripts/python.exe" ] && py="$REPO_ROOT/.venv/Scripts/python.exe"
  [ -z "$py" ] && [ -x "$REPO_ROOT/.venv/bin/python" ] && py="$REPO_ROOT/.venv/bin/python"
  if [ -z "$py" ] || ! "$py" -c "import pytest, mypy, ruff" >/dev/null 2>&1; then
    fatal "no working .venv in this worktree ($REPO_ROOT). Provision it:
    python -m venv .venv && .venv/Scripts/python.exe -m pip install -e \".[dev]\""
  fi
  [ -f "$REPO_ROOT/.env" ] || fatal "no .env in this worktree ($REPO_ROOT). Copy it:
    cp <primary-checkout>/.env \"$REPO_ROOT/.env\""
}

preflight() {
  compat_force_utf8
  export ROADMAP_FILE
  # 2026-09-17: the ECC plugin's session:start hook injected the interactive session's summary
  # ("Worktree: ...\NPCSystem, Branch: remediation-2026-08") into T3.2, which cd'd there and
  # committed into the primary checkout. Silence it for task sessions, and silence
  # stop:session-end so loop sessions stop writing the summaries interactive sessions read.
  export ECC_DISABLED_HOOKS="${ECC_DISABLED_HOOKS:+$ECC_DISABLED_HOOKS,}session:start,stop:session-end"
  mkdir -p "$LOOP_LOG_DIR" "$LOOP_STATE_DIR"
  SESSION_LOG="$LOOP_LOG_DIR/loop-$(date '+%Y%m%d-%H%M%S').log"
  : > "$SESSION_LOG"
  preflight_worktree

  if ! compat_lock_acquire "$LOCK_DIR"; then
    # ISSUE-126. compat_lock_acquire already reclaims a lock whose holder pid is dead, so
    # reaching here means the recorded pid is ALIVE: a real loop, or an MSYS pid reused by
    # an unrelated process after a killed run. Tell the operator how to tell them apart.
    fatal "another loop holds $LOCK_DIR (pid $(cat "$LOCK_DIR/pid" 2>/dev/null || echo unknown)).
  If a loop IS running, stop it first. If none is (a stale lock left by a killed run whose
  pid was reused), check with:  ps -p $(cat "$LOCK_DIR/pid" 2>/dev/null || echo PID)
  then recover with:             rm -rf \"$LOCK_DIR\"   and relaunch."
  fi
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

  # Fail fast on the clock flags, BEFORE the multi-minute baseline seed. Defaulting an
  # unparseable stop time to "stop now" would silently reproduce the bug this replaced.
  clock --next-stop "$STOP_AT" >/dev/null \
    || fatal "unparseable --stop-at '$STOP_AT' (want HH:MM[:SS], or 'none' to disable)"
  [ -z "$START_AT" ] || clock --next-stop "$START_AT" >/dev/null \
    || fatal "unparseable --start-at '$START_AT' (want HH:MM[:SS])"

  if [ "$WITH_SERVICES" = "1" ]; then
    if compat_services_up "$SERVICES_HEALTH_TIMEOUT"; then
      log "preflight: services healthy — integration tests will RUN this night"
    else
      # Never red: an unreachable daemon is infrastructure, not a code regression.
      log "preflight: services unavailable — integration tests will SKIP (degraded, not red)"
    fi
  fi
  compat_ollama_ready && log "preflight: ollama reachable" || log "preflight: ollama not reachable (fine unless a live task runs)"
  # Live-check tasks rebuild the isolated eval stack (scripts/eval_stack_at.sh); without Docker
  # they halt blocked-prerequisite, which skips their phase. Logged, never fatal.
  docker info >/dev/null 2>&1 && log "preflight: docker reachable — live checks can rebuild the eval stack" \
    || log "preflight: docker NOT reachable — live-check tasks will halt and skip their phase"

  log "preflight OK | branch=$START_BRANCH model=$MODEL push=$PUSH_ENABLED services=$WITH_SERVICES"
  log "queue: $(cursor --status | tail -1)"
  report_deferred start
}

# T0B.2: flagged tasks are never dispatched, so say out loud which ones wait on a human —
# at startup (log only, so the tree stays clean) and at the end (into the morning report,
# before checkpoint_reports commits it). A report, not a gate: never fails the run.
report_deferred() {
  local when="$1" out rc=0
  out="$(cursor --audit-deferred 2>&1)" || rc=$?
  if [ "$rc" -eq 0 ]; then log "deferred work ($when): none"; return 0; fi
  log "deferred work ($when): $(printf '%s\n' "$out" | tail -1) — the loop will NOT do these"
  printf '%s\n' "$out" | grep -v '^    ' | grep -v '^DEFERRED_TOTAL=' \
    | while IFS= read -r row; do log "  $row"; done
  if [ "$when" = "end" ]; then
    flag_for_human "deferred tasks the loop skipped (standing debt)" \
      "$(printf '%s\n\n%s' 'Run `make roadmap-audit` to see the line that raised each flag.' "$out")"
  fi
  return 0
}

# T2.4 / DEC-280(a): play the scripted demo live at the end of the night, into the morning
# report next to the deferred-work audit. A report, never a gate — it cannot fail a task,
# touch the red-commit count, or stop the run, and always returns 0. It rebuilds the ISOLATED
# eval stack at HEAD (eval_stack_at.sh --reset), reseeds, and runs `make demo-run-live`.
# make exits 2 on any recipe failure, so the verdict is read from the DEMO_LIVE= line, not rc.
DEMO_LIVE_TIMEOUT_SECS="${DEMO_LIVE_TIMEOUT_SECS:-2700}"
report_demo_live() {
  local logfile rc=0 sha verdict
  if [ "$DRY_RUN" = "1" ]; then log "demo-run-live: skipped (dry run)"; return 0; fi
  if ! docker info >/dev/null 2>&1; then
    log "demo-run-live: stack unavailable (docker not reachable) — not run"; return 0
  fi
  logfile="$LOOP_LOG_DIR/demo-run-live-$(date +%Y%m%d-%H%M%S).log"
  sha="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
  compat_run_timeout "$DEMO_LIVE_TIMEOUT_SECS" "$logfile" bash -c "
    cd '$REPO_ROOT' || exit 2
    { bash scripts/eval_stack_at.sh HEAD --reset && make --no-print-directory eval-stack-seed; } \
      || { echo 'DEMO_LIVE=STACK_UNAVAILABLE reason=eval-stack rebuild or seed failed'; exit 2; }
    make --no-print-directory demo-run-live ARGS='--expect-sha $sha'" || rc=$?
  verdict="$(grep '^DEMO_LIVE=' "$logfile" 2>/dev/null | tail -1)"
  case "$verdict" in
    DEMO_LIVE=PASS*)              log "demo-run-live: $verdict" ;;
    DEMO_LIVE=STACK_UNAVAILABLE*) log "demo-run-live: stack unavailable — $verdict (log: $logfile)" ;;
    *)
      [ "$rc" -eq 124 ] && verdict="timed out after ${DEMO_LIVE_TIMEOUT_SECS}s"
      flag_for_human "live demo broke (make demo-run-live @ $sha)" \
        "$(printf '%s\n\nLog: %s\n\n%s' "${verdict:-no DEMO_LIVE verdict line (rc=$rc)}" "$logfile" \
           "$(grep -v 'HTTP Request' "$logfile" 2>/dev/null | tail -15)")" ;;
  esac
  return 0
}

# ======================================================================================
# clocks
# ======================================================================================
wait_until_start() {
  [ -n "$START_AT" ] || return 0
  local now target delta
  now="$(date +%s)"
  target="$(clock --next-stop "$START_AT")" || return 0
  [ -n "$target" ] || return 0
  delta=$((target - now))
  log "sleeping ${delta}s until $(clock --describe "$target") before starting work"
  sleep "$delta"
}

resolve_stop_deadline() {
  # Resolved ONCE, and only after wait_until_start returns, so --start-at 09:00 gets a
  # deadline of 08:00 TOMORROW rather than one that has already passed.
  STOP_EPOCH="$(clock --next-stop "$STOP_AT")"
  if [ -n "$STOP_EPOCH" ]; then
    log "stop deadline: $(clock --describe "$STOP_EPOCH") — new work will not START past it"
  else
    log "stop deadline: disabled (--stop-at $STOP_AT) — running until the queue drains"
  fi
}

past_stop_deadline() {
  # Compares two absolute epochs, so it is immune to the time-of-day ambiguity that made
  # the old guard exit a 13:21 run instantly. Never interrupts work already running.
  [ -n "$STOP_EPOCH" ] || return 1
  [ "$(date +%s)" -ge "$STOP_EPOCH" ]
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
  # Both prefixes: run_one_task stashes a timed-out task's partial work as 'loop-timeout'
  # and nothing ever pops either kind. Counting one let the other pile up unseen.
  stashes="$(git stash list 2>/dev/null | grep -cE 'loop-auto-restart|loop-timeout' || echo 0)"
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

  # T0.3: every failing test is a harness self-test (tests/unit/scripts/, tests/unit/harness/).
  # Skip-and-log: flag it for the morning, but do NOT count it toward the night-ending
  # MAX_CONSECUTIVE_RED_GATES. Phase-gate routing only — gate_attribution.py is untouched.
  if [ "$cls" -eq 4 ]; then
    flag_for_human "harness self-test red after $phase (skipped, night continues)" \
      "$(tail -40 "$gatelog.class" 2>/dev/null; echo; tail -40 "$gatelog")"
    log "harness self-test red at $phase — logged, not counted (red-gate streak: $CONSECUTIVE_RED_GATES)"
    return 1
  fi

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
  #
  # The boundary itself still launders one task late: run_phase_gate tolerates a red gate
  # (rc=1 falls through to here), and this re-seed then records those failures as the next
  # phase's "pre-existing debt", where gate_attribution.py returns BASELINE_RED for them
  # forever. Suppressing the re-seed is WORSE: a stale baseline makes phase N's failures
  # reproduce as NEW for phase N+1's innocent tasks, and three CONFIRMED verdicts end the
  # night. So the behaviour is deliberately unchanged and the growth is REPORTED instead.
  local before after bfile="$LOOP_STATE_DIR/gate_baseline.json"
  before="$(grep -c '::' "$bfile" 2>/dev/null)"; [ -n "$before" ] || before=0
  log "re-seeding the failing-test baseline for the next phase"
  $PY_RUN "$REPO_ROOT/scripts/gate_baseline.py" --write --note "after-phase-${1:-init}" \
    2>&1 | while read -r l; do log "  $l"; done
  after="$(grep -c '::' "$bfile" 2>/dev/null)"; [ -n "$after" ] || after=0
  log "baseline: $before -> $after already-failing tests"
  if [ "$after" -gt "$before" ]; then
    flag_for_human "gate baseline GREW at phase ${1:-init}" \
      "$before -> $after already-failing tests. Everything newly in the baseline is treated
as pre-existing debt from the next phase onward and is never charged to a task again.
Review before the next run: python scripts/gate_baseline.py --show"
  fi
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
      CONSECUTIVE_BLOCKED_PHASES=0
      [ "$token" = "TASK_COMPLETE_BASELINE_RED" ] && \
        flag_for_human "task $task committed with a pre-existing red gate" \
          "Every failure pre-dated this task (baseline attribution). Nothing new broke."
      return 0 ;;

    PHASE_COMPLETE)
      TASKS_DONE=$((TASKS_DONE + 1))
      CONSECUTIVE_BLOCKED_PHASES=0
      return 10 ;;   # caller runs the phase boundary

    TASK_COMMITTED_REGRESSION)
      # Scar 6.6: do NOT forfeit the phase over one regression.
      TASKS_DONE=$((TASKS_DONE + 1))
      CONSECUTIVE_RED_COMMITS=$((CONSECUTIVE_RED_COMMITS + 1))
      flag_for_human "task $task introduced a confirmed regression" \
        "Committed anyway as visible debt (scar 6.5). Run $CONSECUTIVE_RED_COMMITS of $MAX_RED_COMMITS."
      if [ "$CONSECUTIVE_RED_COMMITS" -ge "$MAX_RED_COMMITS" ]; then
        log "HALT: $CONSECUTIVE_RED_COMMITS regressions committed this run"
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

  local wt_before="$LOOP_STATE_DIR/worktrees-before-$task.json" leaks
  log "--- task $task (phase $phase) -> $tasklog"
  $PY_RUN "$REPO_ROOT/scripts/worktree_guard.py" snapshot > "$wt_before" 2>>"$SESSION_LOG" \
    || log "WARNING: worktree snapshot failed — this task runs without the leak guard"
  run_claude_session "$tasklog" "$CLAUDE_TIMEOUT" "$MODEL" \
    "/expand-linear-next --auto --single-task --phase $phase --task $task"
  rc=$?

  # A task that writes into ANOTHER worktree (the 2026-09-17 T3.2 leak) halts the run. This
  # also trips on your own interactive commits/edits in another worktree during the task.
  if [ -s "$wt_before" ] && ! leaks="$($PY_RUN "$REPO_ROOT/scripts/worktree_guard.py" check "$wt_before")"; then
    flag_for_human "task $task changed another worktree" \
      "$leaks
If that was your own interactive work, restart the loop. Otherwise the task leaked: its
changes are NOT on $(git rev-parse --abbrev-ref HEAD) — reconcile before resuming."
    log "HALT: task $task changed another worktree"
    return 2
  fi

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
  resolve_stop_deadline

  [ "$(cursor --status | tail -1)" ] && log "starting: $(cursor --status | tail -1)"
  seed_gate_baseline "init"

  local next phase task rc
  while :; do
    if past_stop_deadline; then
      log "reached the $STOP_AT stop deadline — not starting new work"; break
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

    # ISSUE-126, root cause. Tasks are ticked by the SESSION (`cursor --mark` inside
    # /expand-linear-next), never by this driver — `grep "cursor --mark" scripts/expand_loop.sh`
    # returns nothing. So a session that returns TASK_COMPLETE without ticking leaves the
    # cursor pointing at the same task, and the loop re-runs it forever. None of the existing
    # caps catch this: they count consecutive RED GATES, REGRESSIONS and BLOCKED PHASES, and
    # this path is none of those — it looks like success. Night one burned 11.45 h this way.
    if [ "$task" = "$LAST_TASK_ID" ]; then
      SAME_TASK_REPEATS=$((SAME_TASK_REPEATS + 1))
      if [ "$SAME_TASK_REPEATS" -ge "$MAX_SAME_TASK_REPEATS" ]; then
        flag_for_human "task $task did not tick itself" \
          "The cursor still points at $task after $SAME_TASK_REPEATS attempts. The session
reported completion but never ran 'roadmap_cursor.py --mark $task', so the work may or may not
be committed. Inspect the last task log before re-running."
        log "HALT: $task repeated $SAME_TASK_REPEATS times without advancing the cursor"
        break
      fi
      log "WARN: cursor still points at $task (attempt $((SAME_TASK_REPEATS + 1)) of $MAX_SAME_TASK_REPEATS)"
    else
      LAST_TASK_ID="$task"
      SAME_TASK_REPEATS=0
    fi

    # DEC-164. `compute_next` enforces no dependency — it skips a flagged task and walks
    # on. A HUMAN GATE says "not yet" where the flags only say "not you". Halting (rather
    # than skipping the phase) is deliberate: every gate's blocked set is downstream of
    # a measurement, so continuing past one means building on a number nobody has taken.
    if ! gates --check "$task"; then
      flag_for_human "HUMAN GATE blocks $task" "see scripts/check_human_gates.py --check $task"
      log "HALT: task $task is behind a closed HUMAN GATE"
      break
    fi

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

  report_deferred end
  report_demo_live
  checkpoint_reports
  log "=== run finished | tasks=$TASKS_DONE phases=$PHASES_DONE skipped=[${SKIPPED_PHASES:-none}] ==="
  log "queue now: $(cursor --status | tail -1)"
  # "UNVERIFIED (" is the cursor's marker template; "[UNVERIFIED:" in prose is not a tick.
  log "UNVERIFIED ticks: $(grep -c 'UNVERIFIED (' "$ROADMAP_FILE" 2>/dev/null) (list them: grep 'UNVERIFIED (' $ROADMAP_FILE)"
  [ -s "$HUMAN_VERIFICATION_FILE" ] && log "REVIEW: $HUMAN_VERIFICATION_FILE"
  return 0
}

main
