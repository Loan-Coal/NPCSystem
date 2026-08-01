#!/usr/bin/env bash
# scripts/loop.config.sh — every project-specific knob the overnight loop needs.
#
# Sourced by scripts/expand_loop.sh BEFORE its own defaults, so anything set here wins,
# and command-line flags win over both. This file plus scripts/loop_gates.py are the two
# files to edit when the project's shape changes.

# ── layout ────────────────────────────────────────────────────────────────────────────
HARNESS_DIR="${HARNESS_DIR:-project-harness}"
ROADMAP_FILE="${ROADMAP_FILE:-$REPO_ROOT/$HARNESS_DIR/ROADMAP.md}"
LOOP_STATE_DIR="${LOOP_STATE_DIR:-$REPO_ROOT/$HARNESS_DIR/.loop-state}"
LOOP_LOG_DIR="${LOOP_LOG_DIR:-$REPO_ROOT/$HARNESS_DIR/.loop-logs}"
# Committed night-shift records (these are project records, not scratch).
HUMAN_VERIFICATION_FILE="${HUMAN_VERIFICATION_FILE:-$REPO_ROOT/$HARNESS_DIR/human_verification.md}"
SOFT_REVIEW_FILE="${SOFT_REVIEW_FILE:-$REPO_ROOT/$HARNESS_DIR/soft_review.md}"

# ── commands ──────────────────────────────────────────────────────────────────────────
PY_RUN="${PY_RUN:-python}"
# The full gate. Measured on this repo: 144 s, 2618 passed / 29 skipped / 87.10 % cov.
GATE_CHECK_CMD="${GATE_CHECK_CMD:-make check}"
# Required whenever a task touches demo_game/ (project rule).
GATE_DEMO_CMD="${GATE_DEMO_CMD:-make test-demo}"
# Roadmap grammar doctor.
GATE_ROADMAP_VERIFY_CMD="${GATE_ROADMAP_VERIFY_CMD:-make roadmap-verify}"

# ── git ───────────────────────────────────────────────────────────────────────────────
# 0 = fully local: commits land on the checked-out branch, nothing is pushed.
# Decided 2026-07-31: stay local until a full night has succeeded.
PUSH_ENABLED="${PUSH_ENABLED:-0}"
# The loop commits onto whatever branch is checked out (upstream kit behaviour, and the
# choice made for this repo). ALLOW_MAIN=0 makes it refuse to start on main anyway —
# a guard against forgetting to branch, overridable with --allow-main.
ALLOW_MAIN="${ALLOW_MAIN:-0}"
DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"

# ── pacing ────────────────────────────────────────────────────────────────────────────
# System timezone measured as Central Europe Standard Time (+02:00).
RESTART_TZ="${RESTART_TZ:-Europe/Paris}"
# Stop STARTING new work past this local time. Never interrupts work already running.
MORNING_STOP_HOUR_LOCAL="${MORNING_STOP_HOUR_LOCAL:-08:00:00}"
# Per-task cap on one implementing claude session (90 min).
CLAUDE_TIMEOUT="${CLAUDE_TIMEOUT:-5400}"
# Cap on one bounded repair session (25 min).
FIX_TIMEOUT="${FIX_TIMEOUT:-1500}"
# Cap on the cheap per-phase soft review (10 min).
REVIEW_SESSION_TIMEOUT="${REVIEW_SESSION_TIMEOUT:-600}"
# Pause after each completed phase, letting subscription headroom regenerate.
PHASE_SLEEP_SECS="${PHASE_SLEEP_SECS:-400}"
# Short breather between tasks.
TASK_SLEEP_SECS="${TASK_SLEEP_SECS:-20}"

# ── models ────────────────────────────────────────────────────────────────────────────
# Decided 2026-07-31: pin implementation sessions to Sonnet. Roadmap tasks carry
# explicit RED anchors and Validation lines, so they are well-specified enough that
# Sonnet lands them, and more tasks fit in a night's quota.
MODEL="${MODEL:-sonnet}"
FIX_MODEL="${FIX_MODEL:-sonnet}"
REVIEW_MODEL="${REVIEW_MODEL:-claude-haiku-4-5-20251001}"

# ── tolerances ────────────────────────────────────────────────────────────────────────
# These decide whether one bad test costs the whole night. Raise only once you have
# seen why they are set here.
MAX_CONSECUTIVE_RED_GATES="${MAX_CONSECUTIVE_RED_GATES:-2}"
MAX_RED_COMMITS="${MAX_RED_COMMITS:-3}"
MAX_CONSECUTIVE_BLOCKED_PHASES="${MAX_CONSECUTIVE_BLOCKED_PHASES:-2}"
RED_COMMIT_TOLERANCE="${RED_COMMIT_TOLERANCE:-1}"
AUTOFIX_ENABLED="${AUTOFIX_ENABLED:-1}"
SOFT_REVIEW_ENABLED="${SOFT_REVIEW_ENABLED:-1}"

# ── services (--with-services; default OFF) ───────────────────────────────────────────
# When enabled, Docker + Neo4j are brought up ONCE at startup so the 31 Neo4j-gated
# integration tests run instead of skipping. A failed boot degrades to skipping and is
# logged; it must NEVER turn the gate red.
WITH_SERVICES="${WITH_SERVICES:-0}"
SERVICES_HEALTH_TIMEOUT="${SERVICES_HEALTH_TIMEOUT:-240}"

# ── usage-limit auto-restart guards (upstream §6.3) ───────────────────────────────────
MAX_USAGE_RESTARTS="${MAX_USAGE_RESTARTS:-4}"
MIN_SECS_BETWEEN_RESTARTS="${MIN_SECS_BETWEEN_RESTARTS:-300}"
USAGE_RESET_SLEEP_SECS="${USAGE_RESET_SLEEP_SECS:-18000}"
MAX_LOOP_STASHES="${MAX_LOOP_STASHES:-3}"
