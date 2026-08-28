#!/usr/bin/env bash
# scripts/loop_compat.sh — Windows/Git-Bash compatibility layer for the overnight loop.
#
# Sourced by scripts/expand_loop.sh. Everything here exists because Git Bash is not
# Linux. Four substitutions, each measured on this machine rather than assumed:
#
#   1. flock          -> compat_lock_acquire  (mkdir is atomic; verified)
#   2. process groups -> compat_tree_kill     (see below — the important one)
#   3. UTF-8 stdout   -> compat_force_utf8    (cp1252 children die on the roadmap's ✅/→)
#   4. setsid/nohup   -> a Scheduled Task or an open terminal; not scripted here
#
# THE TREE-KILL IS THE LOAD-BEARING ONE. Measured: `timeout 3` on a grandchild returns
# rc=124 while leaving the grandchildren running. On Linux the loop relies on process
# groups to reap the tree; here a "timed out" claude session would keep running all
# night — holding the git index, mutating the tree under the NEXT task's session, and
# burning subscription quota. Git Bash exposes the Windows pid at /proc/<pid>/winpid,
# and `taskkill //T //F //PID <winpid>` reaps the whole tree (verified: 3 descendants).
#
# Note the doubled slashes in taskkill flags: MSYS path-mangling rewrites a single
# leading slash into a Windows path, so //T reaches taskkill as /T.

set -uo pipefail

COMPAT_POLL_SECS="${COMPAT_POLL_SECS:-5}"
COMPAT_KILL_GRACE_SECS="${COMPAT_KILL_GRACE_SECS:-2}"
COMPAT_RC_TIMEOUT=124

# --- environment --------------------------------------------------------------------

compat_force_utf8() {
  # Reproduced without this: UnicodeEncodeError: 'charmap' codec can't encode '\u2192'.
  export PYTHONUTF8=1
  export PYTHONIOENCODING=utf-8
  export LC_ALL="${LC_ALL:-C.UTF-8}"
}

# --- single-instance lock (flock substitute) -----------------------------------------

compat_lock_acquire() {
  # Usage: compat_lock_acquire <lockdir>   -> 0 acquired, 1 held by a live process.
  local lockdir="$1" other=""
  if mkdir "$lockdir" 2>/dev/null; then
    echo "$$" > "$lockdir/pid"
    return 0
  fi
  other="$(cat "$lockdir/pid" 2>/dev/null || true)"
  if [ -n "$other" ] && kill -0 "$other" 2>/dev/null; then
    return 1
  fi
  # Stale: the holder is gone. Reclaim.
  rm -rf "$lockdir" 2>/dev/null || true
  mkdir "$lockdir" 2>/dev/null || return 1
  echo "$$" > "$lockdir/pid"
  return 0
}

compat_lock_release() {
  local lockdir="$1"
  [ -d "$lockdir" ] && rm -rf "$lockdir" 2>/dev/null || true
  return 0
}

# --- process-tree reaping (process-group substitute) ---------------------------------

compat_winpid() {
  # Windows pid for an MSYS pid, or empty.
  cat "/proc/$1/winpid" 2>/dev/null || true
}

compat_tree_kill() {
  # Usage: compat_tree_kill <msys_pid>  -> 0 reaped and VERIFIED dead, 1 survivors.
  local msys_pid="$1" winpid=""
  winpid="$(compat_winpid "$msys_pid")"
  if [ -n "$winpid" ]; then
    taskkill //T //F //PID "$winpid" >/dev/null 2>&1 || true
  fi
  kill -9 "$msys_pid" 2>/dev/null || true
  sleep "$COMPAT_KILL_GRACE_SECS"
  if kill -0 "$msys_pid" 2>/dev/null; then
    return 1
  fi
  return 0
}

compat_run_timeout() {
  # Usage: compat_run_timeout <secs> <logfile> <cmd...>
  # Returns the command's exit code, or 124 on timeout (tree reaped first).
  local secs="$1"; shift
  local logfile="$1"; shift
  local child waited=0 rc=0

  "$@" >"$logfile" 2>&1 &
  child=$!

  while kill -0 "$child" 2>/dev/null; do
    if [ "$waited" -ge "$secs" ]; then
      if ! compat_tree_kill "$child"; then
        echo "COMPAT: WARNING tree kill left survivors for pid $child" >&2
      fi
      wait "$child" 2>/dev/null || true
      return "$COMPAT_RC_TIMEOUT"
    fi
    sleep "$COMPAT_POLL_SECS"
    waited=$((waited + COMPAT_POLL_SECS))
  done

  wait "$child"; rc=$?
  return "$rc"
}

# --- optional service preflight (--with-services) ------------------------------------
# Contract: returns 0 when Neo4j is reachable, 1 otherwise. A caller MUST treat 1 as
# "run degraded, integration tests skip" and NEVER as a red gate — an unreachable
# daemon at 2am is infrastructure, not a code regression.

compat_docker_ready() {
  docker info >/dev/null 2>&1
}

compat_start_docker() {
  local waited=0 limit="${1:-180}"
  if compat_docker_ready; then return 0; fi
  powershell.exe -NoProfile -Command \
    "Start-Process -FilePath 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe'" \
    >/dev/null 2>&1 || true
  while [ "$waited" -lt "$limit" ]; do
    sleep 10; waited=$((waited + 10))
    if compat_docker_ready; then return 0; fi
  done
  return 1
}

# Compose invocation for the loop. The test override publishes neo4j's bolt port on
# 127.0.0.1 so host-run integration tests can connect (ISSUE-232 / DEC-232). The base
# file alone puts neo4j on the `internal: true` network only, where a `ports:` stanza is
# silently inert — so without this override every integration test errors with
# ServiceUnavailable and the night's R3 tasks all fail for an environment reason.
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.test.yml"

compat_compose() {
  docker-compose $COMPOSE_FILES "$@"
}

compat_neo4j_healthy() {
  local status
  status="$(docker inspect --format '{{.State.Health.Status}}' \
    "$(compat_compose ps -q neo4j 2>/dev/null)" 2>/dev/null || true)"
  [ "$status" = "healthy" ]
}

# True when bolt is actually reachable from THIS shell, not merely healthy in-container.
# compat_neo4j_healthy asks Docker; this asks the network. They disagreed for months.
compat_bolt_reachable() {
  python - <<'PY' >/dev/null 2>&1
from neo4j import GraphDatabase
d = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
d.verify_connectivity()
d.close()
PY
}

compat_services_up() {
  # Usage: compat_services_up [health_timeout_secs]
  local waited=0 limit="${1:-240}"
  compat_start_docker 180 || { echo "COMPAT: docker did not start" >&2; return 1; }
  compat_compose up -d neo4j >/dev/null 2>&1 || {
    echo "COMPAT: compose up neo4j failed" >&2; return 1; }
  while [ "$waited" -lt "$limit" ]; do
    if compat_neo4j_healthy; then
      export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
      export NEO4J_USER="${NEO4J_USER:-neo4j}"
      export NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
      # Healthy != reachable. Refuse to report success on a container the tests
      # cannot actually connect to — that state produced 34 phantom failures once.
      if compat_bolt_reachable; then return 0; fi
      echo "COMPAT: neo4j healthy but bolt unreachable on localhost:7687 —" >&2
      echo "COMPAT: is docker-compose.test.yml being applied? (ISSUE-232)" >&2
      return 1
    fi
    sleep 10; waited=$((waited + 10))
  done
  echo "COMPAT: neo4j never reported healthy within ${limit}s" >&2
  return 1
}

compat_ollama_ready() {
  curl -s -m 5 http://localhost:11434/api/tags >/dev/null 2>&1
}
