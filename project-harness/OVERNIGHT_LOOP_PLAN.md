# Overnight Roadmap Loop — port analysis & build plan (NPCSystem / Windows)

**Status:** plan only, nothing built. Written 2026-07-31.
**Source:** `project-harness/overnight-roadmap-loop-kit.zip` (extracted from a Linux work repo).

---

## 1. How the kit works

Three cooperating pieces, deliberately separated:

| Piece | What it is | Holds state? |
|---|---|---|
| **The roadmap** | `ROADMAP.md` — numbered phases, task bullets, `✅ DONE` markers | **Yes — the only state** |
| **The skill** | `/expand-linear-next` prompt, run headless via `claude -p` | No |
| **The loop** | `expand_loop.sh` (2384 lines of bash) | No |

**The load-bearing idea:** progress lives *only* as DONE markers in the roadmap, and each
task's commit contains its own DONE marker. The commit **is** the transaction. Kill the loop
at any instant and there is nothing to reconcile — the next launch reads the roadmap, finds
the first unmarked task, continues. No cursor file, no run-state JSON, no session to resume.

**One fresh `claude -p` session per task**, not one long session per night. Bounded context,
no incentive to background slow work, atomic crash recovery.

### The status-token protocol

The skill's last line is a bare `AUTO_STATUS: <TOKEN>`; the loop parses it and branches:

| Token | Loop response |
|---|---|
| `TASK_COMPLETE` | next task |
| `PHASE_COMPLETE` | run the phase boundary (gate → soft review → push → re-baseline → sleep) |
| `ALL_DONE` | finish |
| `TASK_COMPLETE_BASELINE_RED` | gate red but every failure pre-existed → continue |
| `TASK_COMMITTED_REGRESSION` | new confirmed failure → commit + flag, halt after 3 in a row |
| `HALT <reason>` | depends; `blocked-prerequisite` skips the phase rather than halting |

### The red-gate machinery (the non-obvious part)

Naive "gate red → halt" loses whole nights to failures the loop did not cause. The kit splits
four cases:

1. **Baseline** — `gate_baseline.py` snapshots already-failing tests. Written **only at phase
   boundaries**, never mid-phase, so a task cannot launder its own regression into it.
2. **Attribution** — `gate_attribution.py` diffs red gate vs baseline. No new failures →
   `TASK_COMPLETE_BASELINE_RED`, commit and continue.
3. **Confirmation** — `gate_confirm.py` re-runs new failures; only a failure reproducing twice
   is charged to the task. Kills flake-driven halts.
4. **Classification** — `classify_gate_failure.py` routes red to:
   - **HALT-class** (asserts *behaviour*: tests, schema) — never auto-fixed. The easiest way
     to make a red test green is to edit the test, which is fraud.
   - **AUTOFIX-class** (asserts *form*: lint, types, structure) — one bounded
     `/fix-make-failure` session, whose diff is then scanned by `scan_fix_diff.py` for
     gate-gaming (`# noqa`, `# type: ignore`, `except: pass`, edits to tests or gate scripts),
     re-gated, and committed **separately** and flagged.

Tolerance is the point: a still-red gate logs to `human_verification.md` and pushes anyway.
Only `MAX_CONSECUTIVE_RED_GATES` (2) halts.

### §6 — the scars (do not sand off)

Each is a lost night. The ones that bind us hardest:

- **6.1 Never background the gate.** A headless turn ends the moment it stops calling tools;
  a session that backgrounds `make check` dies with work uncommitted.
- **6.2 Commit before you stop.** Next run's clean-tree gate refuses leftovers → work lost.
- **6.5 A red per-task gate must not lose the work.** Commit it, mark `✅ DONE ⚠️ UNVERIFIED`,
  flag it. Visible debt beats lost work.
- **6.6 A regression must not forfeit the rest of the phase.**
- **6.7 Never let the loop's own log be tracked by git.**
- **6.9 Status tokens must not be wrapped in backticks.**
- **6.10 Phase caps must count roadmap state, not tokens.**

---

## 2. Environment delta — Windows

The kit's own porting brief says: *"Recommended: run it under WSL2… A PowerShell rewrite is a
multi-day project."* Both statements are true, and **neither is the right answer here** —
because this project's entire toolchain is Windows-native. What follows is measured, not assumed.

### 2.1 What was actually verified on this machine

| Fact | Result | Consequence |
|---|---|---|
| WSL distros installed | **only `docker-desktop` (Stopped)** | No Ubuntu. WSL2 route = new distro + 2nd Claude auth + 2nd venv |
| Repo location | `C:\Users\lohan\Documents\hackathons\NPCSystem` | Under WSL this is `/mnt/c` — kit explicitly warns it is slow and breaks file watching |
| Running shell | Git Bash (`/usr/bin/bash`, msys 5.2.37) | `flock`, `setsid` **absent** |
| MSYS2 at `C:\msys64` | has `flock.exe`, `setsid.exe` | available, but cross-runtime `msys-2.0.dll` mixing is fragile |
| `timeout`, `nohup`, `date -d` | **present and working** | `date -d "2026-08-01 08:00" +%s` → `1785564000` ✅ |
| `timeout 3 python -c "sleep(30)"` | **rc=124 at 3s** ✅ | direct-child timeout works |
| `timeout` on a **grandchild** | **rc=124 but 5 python procs survived** ❌ | **the critical gap** — see 2.2 |
| `mkdir` lock atomicity | second `mkdir` correctly refused ✅ | valid `flock` substitute |
| `claude` CLI from bash | `/c/Users/lohan/AppData/Roaming/npm/claude` (+ `.cmd`, `.ps1`) | invokable directly ✅ |
| Python stdout encoding | **`UnicodeEncodeError` on `→` under cp1252** ❌ | see 2.3 |
| `ROADMAP.md` line endings | **1173 CRLF, 0 bare LF**; `core.autocrlf=false`, no `.gitattributes` | see 2.4 |

### 2.2 HAZARD — orphaned process trees (highest risk)

`timeout` reports 124 and returns control, but **the child's children keep running**. On Linux
the kit relies on process groups + signal semantics to reap the tree. Here, a hung `claude`
(node) session would be "timed out" from the loop's view while still running: holding the git
index, mutating the working tree under the *next* task's session, and burning subscription quota
all night. This is a §6-class night-loser that does not exist in the source environment.

**Substitute:** launch the session recording its PID, and on timeout escalate to a Windows-native
tree kill — `taskkill //T //F //PID <pid>` — then verify no `claude`/`node` survivors before the
next task starts. This must be a *verified* reap, not a best-effort signal.

### 2.3 HAZARD — UTF-8 stdout

Reproduced during analysis: a plain `python` script printing roadmap content dies with
`UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'`. The roadmap is dense with
`—`, `→`, `✅`, `⚠️`, `🔶`, `⏸️`. Every helper script and every `make` invocation the loop makes
must run with `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` exported. Unset, the cursor crashes on
the first `--slice`.

### 2.4 HAZARD — CRLF whole-file rewrites

`roadmap_cursor.py:93` reads via `path.read_text(...)` (universal newlines → `\r\n` collapses to
`\n`) and `:101` writes via `write_text(...)`. On the Linux source this is a no-op. Here, **every
single `--mark` would rewrite all 1173 lines from CRLF to LF**, turning each task commit into a
whole-file diff — destroying reviewability and the "commit is the transaction" property.

**Fix (2 lines):** read with `open(..., newline='')`, write with `newline=''`. Add a regression
test asserting a `--mark` round-trip changes exactly one line.

### 2.5 Substrate recommendation

**Run on Git Bash, single working copy, no WSL.** Rationale: venv (`.venv/Scripts/python.exe`),
`make`, Docker Desktop, Ollama, and the authenticated `claude` CLI are all Windows-native and
already working. WSL2 buys kit fidelity at the cost of a second Claude auth, a second venv, a
`/mnt/c` filesystem boundary, and a divided repo — for a gate that is 100% Windows Python.

This is **not** the "PowerShell rewrite" the kit warns against. It is the kit's bash, with four
substitutions: `flock`→`mkdir` lockdir, `setsid`→Scheduled Task (or just leave the terminal open),
tree-kill→`taskkill //T //F`, plus forced UTF-8. Everything else — the loop skeleton, the token
protocol, all of §6 — ports intact.

**Also required:** disable Windows sleep / set the power plan to stay awake on AC. An overnight
run dies at the first suspend.

---

## 3. Project delta — this is not the source repo

### 3.1 The roadmap does not parse, and must not be pointed at as-is

The kit's grammar is `## Phase <int>:` + `- **N.M —` + `✅ DONE`. This project uses
`### Phase <STRING> — …` + `- [ ] **<ID>** …` with **markdown checkboxes** as the done marker,
where IDs are strings: `EVAL-P0.2`, `PR-9`, `REM-W3`, `PERF-3`.

Worse, the scoping problem. Measured across all 1173 lines — **45 open, 121 done**:

| Section | Open tasks | Safe to auto-attempt? |
|---|---|---|
| `## Active — Eval pipeline (EVAL-P0..P7)` | **26** | ✅ **yes — the current program** |
| `## Active — Folder reorganisation` (PR-9) | 1 | ❌ marked *optional*, deferred |
| `## Next+1 — …` Phase EVAL / Phase PERF | 13 | ❌ not started, gated on earlier work |
| `## Next — …` Open decisions | 1 | ❌ it is a *question*, not a task |
| `## Completed ✅ — F/G/H` Phase H | 2 | ❌ **inside a section titled Completed** |
| `## Parked backlog` | 2 | ❌ parked by definition |

A naive cursor would cheerfully start Phase PERF, or a leftover Phase H bullet, at 3am. **19 of
45 open tasks are traps.** This is the single biggest porting risk and it is a *content* problem,
not a code problem.

**Fix:** an explicit machine-readable queue fence in `ROADMAP.md` —
`<!-- LOOP:QUEUE start -->` / `<!-- LOOP:QUEUE end -->` around the active program — plus a
per-task `⏸️` opt-out. The cursor sees nothing outside the fence. Explicit beats heuristics
("only `## Active`" would still have swept up PR-9).

### 3.2 Task granularity: this project's tasks are *better* than the kit's

The kit asks for "an explicit acceptance criterion". This roadmap already exceeds that — each
task carries `Files:`, a **`RED anchor:`** (the exact test that must fail first, and why), and
`Validation:`. Example, EVAL-P0.2:

> RED anchor: `tests/unit/evals/test_src_free.py::test_only_engine_adapter_imports_npc_engine`
> fails because `retrieval_runner` still names `npc_engine`.

That is a near-ideal unattended work unit. **Recommendation: adopt the kit's one-task-per-session
granularity**, not the current `/expand-next` one-phase-per-session — these phases hold 2–5
heavy tasks and would blow the 90-minute timeout.

### 3.3 Two halt classes the kit does not have

- **`⚠️ ask-gate`** — the roadmap explicitly tags tasks needing a human call (EVAL-P0.1,
  EVAL-P0.3 "edits the shared `make check` health gate"). Reinforced by CLAUDE.md's *Asking
  before doing* (public interface, new dependency, graph schema, CI, file deletion, layer
  violation). These must **skip like §6.4 blocked-prerequisite** — never auto-decided, never
  night-ending. Leave unmarked so a later run retries after you answer.
- **`(live)` tasks** — EVAL-P0.4 needs engine + Neo4j + Ollama + three seeded worlds and is
  explicitly *not* `make check`-gated. Skip-class unless a preflight confirms the services.

### 3.4 Gate mapping — the project is *richer* than the kit here

`make check` = `lint · check-rules · check-layers · check-docstrings · type · check-harness · test-cov`.
Integration tests **skip cleanly** without `NEO4J_*` env vars (verified), so the gate is
offline-capable. Last known green: 2,618 passed, 29 skipped, 87.10% coverage.

| Kit slot | This project |
|---|---|
| `GATE_CHECK_CMD` | `make check` |
| `GATE_PRINCIPLES_CMD` | **drop `check_principles.py` entirely** — `check_rules.py` (ratcheted), `check_layers.py`, `check_docstrings`, `check_harness_honesty.py` already do this, better and project-tuned |
| `GATE_ROADMAP_VERIFY_CMD` | new `make roadmap-verify` → `roadmap_cursor.py --verify` |
| — | **new:** `make test-demo` required whenever `demo_game/` is touched |

**HALT-class** (behaviour): `pytest tests/ -q`, `make check-contracts`, `make check-contract-sync`,
and the ≥80% coverage assertion.
**AUTOFIX-class** (form): `make lint`, `make type`, `make check-rules`, `make check-layers`,
`make check-docstrings`, `make check-harness`.

### 3.5 A gate-gaming vector unique to this project

`scan_fix_diff.py`'s frozen-path list **must** include `scripts/rules_baseline.txt` and
`scripts/mypy_ratchet.py`. The project ships `make check-rules-update`, which *legitimately*
rewrites the violation baseline — an autofix session that runs it launders every new violation
into "expected" and the gate goes green having fixed nothing. Same for `Makefile` and `tests/`.
The source repo has no ratchet, so the kit's list does not cover this.

### 3.6 What already exists here and should be retired

`project-harness/run-roadmap-loop.sh` + `.loop-prompt.txt` — a 40-line phase-granular loop with
`LOOP_CONTINUE`/`LOOP_DONE`/`LOOP_HALT` tokens, `MAX_ITERS=12`, no baseline, no attribution, no
autofix, no pacing, halts on any red gate. It is the naive design the kit's §6 exists to correct.
Supersede it; keep `.loop-logs/` gitignored (already is — `.gitignore:1-2`, satisfying §6.7).

---

## 4. Build plan

Ordered so each step is verifiable before the next. Steps 1–4 involve **no model calls**.

### Step 0 — Roadmap surgery (prerequisite, do first)
Fence the queue with `<!-- LOOP:QUEUE -->` around EVAL-P0..P7. Confirm the 19 trap tasks fall
outside it. Normalise any task bullet whose bold ID is not cleanly delimited (e.g.
`**PR-9 (optional) \`graph/repositories/\`**`). *Deliverable: a roadmap `--verify` can accept.*

### Step 1 — Port the cursor (`scripts/roadmap_cursor.py` + `_roadmap_cursor_core.py`)
Rewrite the four grammar constants for string phase IDs, checkbox done-markers, and the queue
fence; phase ordering becomes **file order** (IDs are not numeric). Fix the CRLF I/O (§2.4).
Ship unit tests: parse, next, slice, mark round-trip (**exactly one line changes**), verify,
fence-exclusion. *Deliverable: `--verify`, `--next`, `--slice`, `--mark` correct on the real
1173-line roadmap.* This is the highest-value step and is pure Python — no bash, no Windows risk.

### Step 2 — Gate wiring
Add `make roadmap-verify`. Write `scripts/loop_gates.py` with the §3.4 HALT/AUTOFIX split and
the §3.5 frozen paths. Port `gate_baseline.py`, `gate_attribution.py`, `gate_confirm.py`,
`scan_fix_diff.py` (near-unchanged). Confirm each command exits 0 by hand.

### Step 3 — Windows compat layer (`scripts/loop_compat.sh`)
Four substitutions from §2.5: `mkdir` lockdir with stale-PID reclaim; `taskkill //T //F` tree
reap with survivor verification; forced UTF-8 env; detach strategy. *Deliverable: a test proving
a timed-out grandchild is actually dead.*

### Step 4 — Dry-run harness (the kit's §7.5 trick — do not skip)
Throwaway repo, stub gates that `exit 0`, and a **fake `claude` earlier on `PATH`** that marks a
task done, commits, and echoes `AUTO_STATUS: PHASE_COMPLETE`. The whole loop — config, cursor,
gate, attribution, boundary, sleep — runs end to end in ~1 minute with **zero model calls**.
This catches the unbound-variable and path errors that otherwise only appear at 3am.

### Step 5 — Port the loop + skills
`expand_loop.sh` with the CTF machinery deleted (`--smoke`, `run_review_cycle`, `_smoke_run_one`
— keep the `REVIEW_SESSION_TIMEOUT` variable, reused by the generic soft-review filer). Adapt
`expand-linear-next.md` from the existing `/expand-next` (keep `/expand-next` untouched for
interactive use), adding: task-granularity, the bare-token contract (§6.9), the
never-background-the-gate emphasis (§6.1), and the two new halt classes (§3.3). Port
`fix-make-failure.md` and `clean-slate.md`.

### Step 6 — Bring-up, in this order
`--max-tasks 1` foreground, watching → `--max-phases 1` → a real night, **`--no-push` first**.
Turn pushing on (`origin` = `github.com/Loan-Coal/NPCSystem.git`) only after a full local night
has succeeded.

---

## 5. Decisions — RESOLVED 2026-07-31

1. **Substrate: Git Bash + compat layer.** ✅
2. **Granularity: one task per session.** ✅ New `expand-linear-next` skill; `/expand-next` stays
   untouched for interactive use.
3. **Push policy: local-only (`--no-push`).** ✅ Revisit only after one full night succeeds.
4. **Autofix: enabled**, bounded to one repair session per red gate, diff-scanned, committed
   separately and flagged. ✅ Frozen paths per §3.5.

5. **Service orchestration: preflight-only, `--with-services` default OFF.** ✅ See §6.

### 5.1 Why Git Bash over MSYS2, long term

Both are installed: Git Bash (`C:\Program Files\Git`, 378 binaries) and a full MSYS2
(`C:\msys64`, 488 binaries, with `pacman`). They ship **different `msys-2.0.dll` builds** —
Aug 2025 / 3,355,762 B vs Jan 2026 / 3,358,849 B. These are separate Cygwin-derived runtimes;
loading one's binaries into the other's process tree is the classic cygheap-mismatch / fork
failure. **Borrowing `flock.exe` from `C:\msys64` into Git Bash is permanently off the table.**
Current PATH has `/c/msys64/ucrt64/bin` + `/c/msys64/mingw64/bin` (native MinGW binaries — safe)
but **not** `/c/msys64/usr/bin` (msys runtime). Keep it that way.

| Axis | Git Bash | MSYS2 |
|---|---|---|
| Agent toolchain parity | **Claude's Bash tool *is* Git Bash** — future sessions debug the loop in the shell it runs in | Loop runs where no agent session can natively reproduce it |
| Package availability | Fixed set; new tools = native equivalents | `pacman` — wins outright if the loop grows |
| Upgrade risk | Rides Git-for-Windows updates; boring | `pacman -Syu` can need staged core updates |
| Portability to WSL/Linux later | Plainer POSIX, ports cleanly | Accretes MSYS2-only assumptions |
| `flock` / `setsid` | absent → `mkdir` lockdir + Scheduled Task | native |
| **Orphaned process trees** | **unsolved — needs `taskkill //T //F`** | **unsolved — needs `taskkill //T //F`** |

The last row decides it. MSYS2's headline advantage addresses the *least* consequential gap;
the gap that actually loses nights (§2.2) is identical in both, because neither can reap a
native Windows process tree via POSIX signals. Agent-toolchain parity compounds over months of
maintenance. Adopt MSYS2 only if pacman-only tooling becomes genuinely necessary — and then
migrate **wholesale**, never mix.

---

## 6. Live services — Docker, Neo4j, Ollama (decided 2026-07-31)

Measured on this machine:

| Fact | Value |
|---|---|
| GPU | RTX 5070 Ti Laptop, **12,227 MiB** |
| `mixtral:8x7b` | **26.44 GB** → exceeds VRAM → CPU/offload inference |
| `qwen2.5:7b` | **4.68 GB** → fits GPU comfortably → fast |
| `qwen2.5:14b` / `cyoa-lora` | 8.99 GB / 4.68 GB (present, unused by the gate) |
| Ollama | **already running** as a Windows service (responds on `:11434`) |
| Docker Desktop | not running at time of survey |
| Neo4j-gated tests | 16 files, **31 test functions** ≈ the whole 29-skip population |
| Neo4j healthcheck | present; `start_period 20s`, `retries 20` → ~220 s worst-case wait |
| Existing helpers | `make boot-check`, `e2e/scripts/boot_check.py` |

`make check` is **fully offline today** — the only `11434` references in `tests/` are URL strings
for object construction and URL-safety validation, not live calls.

### 6.1 Tier A — the per-task gate stays offline

**Do not add Neo4j to `make check`.** Three reasons; the second is the night-killer:

1. **Shared mutable state.** All 31 integration tests share one graph. Task N's residue fails
   task N+1 — manufacturing exactly the flake class `gate_confirm.py` exists to survive.
2. **Infra failure masquerades as regression.** If Docker is down at 2am, pytest reports
   failures, `classify_gate_failure.py` routes them HALT-class, and the night ends over a
   daemon. **Service unavailability must never be able to look like a code regression.**
3. **Cost.** The inner gate runs ~90× a night.

### 6.2 Tier A′ — optional startup preflight (`--with-services`, default OFF)

If enabled, **once at loop startup, never per task**: start Docker Desktop → poll `docker info`
→ `docker-compose up -d neo4j` → wait on the compose healthcheck → export `NEO4J_*` → **re-seed
the gate baseline** so the 31 newly-running tests enter it properly.

**Hard rule: if boot fails, degrade to skipping and log it — never go red.**

Default OFF for EVAL-P0..P7: that program is evals / statistics / scorers / CLI, nearly pure
Python, so un-skipping 31 *graph* tests buys little and adds real flake surface. Enable it when
a roadmap program actually touches `graph/`.

### 6.3 Tier B — Ollama needs no boot

Already running as a Windows service. Health-check only. `qwen2.5:7b` (4.68 GB) fits the 12 GB
GPU, so the engine's own generation path is fast enough to be loop work.

### 6.4 Tier C — the mixtral judge is NOT loop work

`mixtral:8x7b` at 26.44 GB cannot fit 12 GB VRAM → CPU inference. It is MoE (~12.9B active
params/token); on laptop memory bandwidth that is low single-digit tok/s → tens of seconds per
judge call. EVAL-P0.4 is 53 cases × k repeats: one task would consume the entire night.

**The roadmap already solves this.** DEC-144 / EVAL-P1 is explicitly two-phase
generate→judge with generate-once / judge-many. That splits along the hardware boundary:

| Work | Where it runs |
|---|---|
| Code tasks (P0.2, P0.3, P1.*, P2.*, P3.*…) | **overnight loop** — offline, `make check`-gated |
| Generation runs (`qwen2.5:7b`, GPU) | overnight-capable |
| **Judging (`mixtral`, CPU)** | **deliberate batch, never loop work** |

EVAL-P0.4 is already tagged `(live; not make check-gated)` in the roadmap, so it is already
skip-class under §3.3. Roadmap and hardware constraint agree.

**Flagged, not decided:** a judge fitting 12 GB would make overnight judging viable, but
EVAL-P0.1 froze the judge at `mixtral:8x7b` *"so the EVAL-P0.4 baseline stays comparable to the
Stage-A counts."* Changing it is a `DECISIONS.md` call, not a loop-design call.
