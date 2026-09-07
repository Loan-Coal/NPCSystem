---
description: Full codebase + demo review (night run). Fans out read-only reviewer agents across 10 lenses (engines AND demo_game), synthesizes findings, and regenerates the /fix-next + /fix-parallel backlog. Weighted toward the small-model goal - engine portfolio, LLM dependence, prompts, runtime coupling.
argument-hint: "[--inline] [--allow-dirty] [--lenses L1,L11,L12]  (optional; default = all lenses, parallel)"
---

You are the ORCHESTRATOR of a full, regression-aware review of the WHOLE codebase —
both the engine (`src/npc_engine/`) and the demo (`demo_game/`). You do **not** fix
anything. Your single job is to produce a triaged findings report plus a remediation
backlog that `/fix-next` and `/fix-parallel` can consume directly. Work LEAN; keep all
summaries terse; never paraphrase files back to me.

This is designed to run **autonomously overnight** ("night run"): dispatch read-only
reviewer subagents in parallel, let them write per-lens evidence, then synthesize. The
review is **read-only** — neither you nor any worker edits source code, only the review
artifacts under `project-harness/`.

**The standing goal this review serves: a small local model producing great effects.**
Findings that shrink what the model must do, or that let a smaller model do it, outrank
findings that merely tidy code. L10–L13 exist for that; weight them accordingly in §4 §3.

## Invariants (never violate)
1. **Read-only.** No source edits, no commits to `src/` or `demo_game/`. The only files
   written are the review artifacts in §6. Workers are explicitly read-only.
2. **Regression-aware.** Every prior fix must be re-verified, not assumed. Each lens opens
   its evidence file with a re-verification table of the prior SEVs in its own area
   (HOLDS / PARTIAL / REGRESSED), read from the newest archived review (§1).
3. **Cover both halves.** A finding set that ignores `demo_game/` is incomplete. L6 owns
   the demo; L9 actually runs it. Engine-only is a failed review.
4. **Output format is a contract.** `/fix-next` and `/fix-parallel` read
   `project-harness/review-fixes/INDEX.md`, the `FIX-<SEV>.md` briefs, and
   `project-harness/REVIEW_FINDINGS.md`. Produce exactly those, exactly there.
5. **One reality check.** Asserted-not-measured is the recurring failure of past reviews:
   a guard test that verifies a constant in isolation while the real path is unprotected.
   Prefer "I ran it / I traced the call site" over "the test exists."
6. **Never quote a judged eval number as quality.** The scorer layer is under repair: all
   five scorers are REFUSED by `scripts/check_label_adequacy.py`, the label set is NOT
   FROZEN, and panel kappa has swung 0.58 → 0.83 between runs. Deterministic matchers
   (schema, keyword, in_set, substring), latency stats, retrieval metrics and
   `engine_status` liveness/timing ARE usable. A rate your own trust policy would refuse is
   worse than no rate — it gets requoted later with the caveat stripped (ISSUE-275, -283).
7. **Do not re-log a known issue.** `project-harness/ISSUES.md` holds 100+ open entries.
   Every candidate Log finding is checked against it before it becomes a new ISSUE-NNN.

## 1. Baseline + prior-art (do first, cheaply)
- `git status` should be clean. If dirty and `$ARGUMENTS` lacks `--allow-dirty`, STOP and
  tell me — a review of a dirty tree is noise. With `--allow-dirty`, proceed but paste the
  `git status --short` output verbatim into the report header and tell every worker which
  paths are in flight, so a finding against uncommitted work is labelled as such.
- Record date, branch, and HEAD commit for the report header.
- Read the newest archived review for regression context: the most recent
  `project-harness/archive/review-*/` by directory date (do NOT assume which — list them).
  Its severity table and systemic-patterns section become each lens's re-verification list.
- If a CANONICAL review already exists (`project-harness/REVIEW_FINDINGS.md` or a non-empty
  `project-harness/review-fixes/`), archive it first: move both into
  `project-harness/archive/review-<its-date>/` so this run writes fresh. Note the move.

## 2. The lenses (10; each → one read-only worker)
Every lens worker writes ONE evidence file to `project-harness/review-fixes/evidence/<Lx>.md`
with this shape: a re-verification table of relevant prior SEVs (HOLDS / PARTIAL / REGRESSED),
then findings, each as `### [Lx-NN] <title>` + `Severity: CRITICAL|HIGH|MEDIUM|LOW · Confidence:
Confirmed|Likely|Suspected`, with **file:line evidence** and a one-line fix sketch. No fixes.

**L3 (types), L5 (cleanliness) and L8 (regression sweep) are RETIRED.** Their ids are not
reused — old `L3-NN`/`L5-NN`/`L8-NN` finding ids must keep pointing at what they always did.
L3 and L5 were re-deriving what `make check` already proves (mypy, Pydantic boundaries,
Literal sets, file/function size, nesting, docstrings); their one ungated half — dead surface
— moved into L10. L8's mechanical prior-SEV sweep is now invariant 2, owned per-lens.

| Lens | Agent (`subagent_type`) | Scope |
|------|-------------------------|-------|
| **L1 Security** | `security-reviewer` | `auth/`, `api/`, `config/`, LLM/Neo4j boundaries: input caps (`MAX_PLAYER_MESSAGE_CHARS`, `delta_ticks` bounds), auth on every non-`/health` route, prompt-injection, secret handling, error-message leakage, WS connection cap actually enforced. |
| **L2 Architecture** | `architect` | Layer model (run `make check-layers`), DIP (engines import protocols not concretes), no LLM in `graph/`/`retrieval/`, no Neo4j outside `graph/`, no prompt strings outside `prompts/`, single composition root, session ownership. Also: are the ~40 `engines/ports/*` Protocols right-sized against the repo's own rule (abstract at 2+ implementors or 3+ callers)? Any god-port, any port with one caller? |
| **L4 Tests & efficacy** | `code-reviewer` | Coverage gaps, **asserted-not-measured** guard tests, mock validity (LSP: mocks match real adapter contract), Neo4j-touching code has real integration tests, LLM code has mock-adapter tests. Name any test that would still pass against a deliberately broken implementation, and any test that greps source text rather than exercising behaviour. |
| **L6 Demo / product** | `general-purpose` | **`demo_game/` correctness** (zero `src/` imports), `client.py` API calls match live routes, win/lose reachability in `game_end_checker.py`, poller/panel wiring, scenario integrity (`run.py`/`run_scenes.py`), branch/economy/content depth, `make test-demo` health. Plus product-level engine gaps. |
| **L7 OCP / expansion** | `architect` | Open-Closed seams for the roadmap: new LLM backends, distortion types, emotion models, location hierarchy — added by NEW file, never editing a closed module. Flag any variant that requires editing an existing engine. |
| **L9 Live verification** | `general-purpose` | Actually RUN it: `make check`, `make test`, `make test-demo`, `make demo-run ARGS=--dry-run`, container-boot sanity. Then hit `GET /v1/admin/system/metrics` after a couple of dialogue turns and report the new `llm_backend_*` observations (DEC-273) — including whether `llm_backend_load_latency_seconds` min is ~0, i.e. whether `keep_alive` is actually holding the model. Report what is red on the current tree. |
| **L10 Portfolio & dead surface** *(keep this one CHEAP)* | `general-purpose` | **One table, one row per engine dir under `engines/`**: wired into `scheduler/tick_scheduler.py`? reachable from a route? touched by `demo_game/`? exercised by any `evals/cases/*`? → verdict `keep` / `merge` / `stub` / `delete-candidate`. Call out known-shape duplicates (`oath` and `treaty` are both expiry+violation; `agenda`/`succession`/`faction_politics` are all political tallies) and confirmed stubs (`military` is a documented no-op). Then a mechanical dead-surface sweep: `Settings` fields with no reader, prompt YAMLs no code loads, functions with no caller, `engines/contracts/*.yaml` vs `*/llm_config.yaml` mismatches. Evidence + verdict only — do NOT deep-review any engine's logic; that is L2/L4's job. |
| **L11 LLM dependence** | `architect` | The LLM call sites are the whole small-model question. Enumerate every one (start from `engines/*/llm_config.yaml` and every `generate`/`generate_structured`/`stream` call). Per site: what cognitive demand does it place on the model — classification, structured extraction, or open generation? Could it be deterministic instead (`engines/gossip/` is the in-repo precedent: seeded distortion, no model)? Is it on the interactive path or a background tick? What does the player see when it fails, and is that fallback acceptable? Retry amplification (`quest_generation` does 3 attempts, dialogue 2). Declared vs enforced timeouts. **Close with: which call sites would survive a 3B, which need the 7B, and why.** |
| **L12 Prompt** | `general-purpose` | `src/npc_engine/prompts/` **content** — reviewed by nobody until now. The dialogue system prompt is ~4,245 static tokens of 17 rules on every turn: find rule conflicts, redundancy, and rules the model demonstrably ignores. Cross-check the Output-rules block against the generation schema — it instructs 4 of 13 fields, and `facial_expression` is consumed by the demo and by evals with no prompt rule at all. Check length guidance against `max_tokens`, injection-resistance rules against L1, prompt/version/hash discipline, and dead prompts (`slot_fill_v1.yaml`, `flavor_v1.yaml`). **Ask throughout: what could a smaller model absorb into weights, and what must stay in the prompt?** NOTE: any prompt edit changes `dialogue_prompt_hash` and breaks eval comparability — flag, never propose blindly. |
| **L13 Runtime coupling & load** | `general-purpose` | The runtime graph, which L2's static import graph cannot see. (a) **Tick-order coupling**: `ENGINES.md` says the scheduler runs engines in a fixed order so upstream state is visible downstream in the same tick — map who actually reads what another engine wrote this tick, and name every undocumented ordering dependency. (b) **Silent-failure census**: engines are exception-isolated, `engine_status_store` records `last_error`, and nothing reads it — advance the clock and report which engines are no-oping. (c) **Load**: unbounded `asyncio.gather` (chapter has 3 nested, only 2 sites repo-wide are semaphore-bounded), LLM serialisation on one resident model with no queue, `TICK_LLM_CALLS_PER_MINUTE_MAX` declared and never enforced, unbounded graph append (ISSUE-279), per-engine Neo4j query count per tick. May use `make eval-stack-up` for timing and liveness — **deterministic and timing data only, per invariant 6.** |

If `$ARGUMENTS` contains `--lenses L1,L11,...`, run only those. Otherwise run all 10.

## 3. Dispatch (parallel, background, read-only)
Unless `$ARGUMENTS` contains `--inline`, launch one `Agent` per lens with
`run_in_background: true`, **capped at 4 concurrent** (dispatch the next as earlier ones
report). Use `model: sonnet` for the static lenses (L1, L2, L4, L6, L7, L10, L11, L12);
L9 and L13 run things and may use the default. Each worker prompt MUST say:

> READ-ONLY review. Do NOT edit any source file, do NOT commit. Obey `project-harness/CLAUDE.md`
> as the rubric (layer model, file/function limits, Pydantic boundaries, typed/Literal fixed
> sets, structured logging, auth+input-caps, fallback contracts). Re-verify the prior SEVs I
> list, then hunt new issues. Cite file:line for everything. Write your evidence to
> `project-harness/review-fixes/evidence/<Lx>.md` in the required shape. Prefer "I ran/traced
> it" over "the test exists" — call out asserted-not-measured. Do NOT quote any judged eval
> score as evidence of quality: all five scorers are currently REFUSED by the adequacy floor.
> The standing goal is a small local model producing great effects — prefer findings that
> shrink what the model must do. Return: counts by severity, your 3 highest-severity finding
> ids, and anything that needs a human decision (schema/dependency/interface).

For `--inline`: skip subagents and work each lens yourself in sequence, writing the same
evidence files. Slower, no spawn cost.

## 4. Synthesize → REVIEW_FINDINGS.md
When all lenses report, read the evidence files and write `project-harness/REVIEW_FINDINGS.md`:
- **Header**: date, branch, HEAD, "Mode: 10-lens parallel review (engines + demo)",
  prior-review pointer, and — if `--allow-dirty` — the verbatim `git status --short`.
- **§1 Verdict**: one paragraph — is the tree release-clean? Lead with any CRITICAL.
- **§2 Severity counts** table (CRITICAL/HIGH/MEDIUM/LOW with the lens-prefixed ids).
- **§3 Systemic patterns**: root-cause clusters across lenses (the high-value section).
  Lead with anything from L10–L13 that shrinks the model's job.
- **§4 Triage table**: every finding → `id | sev | title | lens | disposition` where disposition
  is **Fix now** / **Log** (defer to ISSUES.md) / **Decide** (needs my call: schema, dependency,
  interface change). Assign each Fix-now/Log finding a fresh monotonic **SEV-NN**.
- **Before assigning any disposition**, grep `project-harness/ISSUES.md` and
  `archive/ISSUES_RESOLVED.md` for each finding. A finding that duplicates an open issue is
  dropped from the backlog and listed in a **§5 Already known** table as
  `finding → ISSUE-NNN`. A finding that contradicts a resolved issue is a REGRESSION and is
  promoted, not dropped.
- **§6 Confidence ledger**: count findings by Confirmed / Likely / Suspected. Nothing graded
  **Suspected** may be dispositioned Fix-now — it is Log or it is verified first.

## 5. Generate the fix backlog (the /fix-* contract)
- Create `project-harness/review-fixes/INDEX.md`: a **Carry-forward notes** block at the top
  (≤10 lines, starts empty), then an ordered `[ ]` checklist of every **Fix-now** SEV grouped
  into dependency blocks (A–F style), each line: `[ ] SEV-NN — <title>  (deps: …, file set: …)`.
  Mark **Decide** items clearly as blocked-pending-approval; **Log**-only items go to ISSUES.md, not here.
- For each **Fix-now** SEV write a self-contained `project-harness/review-fixes/FIX-SEV-NN.md`:
  **Problem**, **Current shape** (cited files+lines, verified against the code now), **Steps**,
  **Verification** (a concrete unit test + the exact command — e.g. `pytest tests/unit/<...>` then
  `make check`/`make test-demo`), **Blast radius**. A cold worker must need nothing but this brief
  and its cited files.
- For **Log** findings, append `ISSUE-NNN` entries to `project-harness/ISSUES.md` (monotonic id —
  check BOTH `ISSUES.md` and `archive/ISSUES_RESOLVED.md`, per `make check-ledger-ids`). For
  **Decide** findings, append a `DECISIONS.md` question stub.

## 6. Artifacts written (and ONLY these)
- `project-harness/REVIEW_FINDINGS.md`
- `project-harness/review-fixes/INDEX.md`
- `project-harness/review-fixes/FIX-SEV-*.md`  (one per Fix-now item)
- `project-harness/review-fixes/evidence/{L1,L2,L4,L6,L7,L9,L10,L11,L12,L13}.md`
- appended entries in `project-harness/ISSUES.md` (Log) and `DECISIONS.md` (Decide)
Commit them in one `docs(review): full codebase+demo review <date> — findings + fix backlog`
commit on the current branch. No source changes in this commit. If `--allow-dirty` was used,
stage ONLY the review artifacts — never the in-flight work.

## 7. Stop
STOP. In ≤10 lines: the verdict (release-clean? any CRITICAL), severity counts, how many
findings were dropped as already-known, the count of Fix-now SEVs in the backlog, the single
highest-value small-model finding from L10–L13, anything flagged **Decide** (needs my call),
and the next step ("run `/fix-parallel` for the parallelizable batch, `/fix-next` for
serial/blocked items"). Do NOT start fixing — that is `/fix-next`'s job.
