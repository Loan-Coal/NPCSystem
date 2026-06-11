# NPC Engine — Final Hardening & Readiness Review (orchestration prompt)

**Created:** 2026-06-04 · **Mode:** phased w/ checkpoints · **Structure:** parallel split-role agents · **Depth:** static + live verification.

This is the reusable prompt/spec for the final review after the 2026-06-03 review
(`REVIEW_FINDINGS.md`, 43 SEV briefs) was remediated. The goal is **completion**:
prove the prior fixes hold, find anything new, and confirm the codebase is clean,
secure, hardened, and ready for expansion. Token cost is not a constraint.

---

## 0. Acceptance criteria ("done" definition)

The review is complete only when ALL of the following are true and evidenced:

- `make check` fully green: `lint` (0 new vs `scripts/rules_baseline.txt`), `type`
  (mypy 0), `check-layers`, `check-docstrings`, `check-rules`, `test-cov` ≥ 80%.
- `make test` green, OR every remaining failure (see ISSUE-056's "8 pre-existing")
  is either fixed or explicitly re-classified with an owner decision.
- `make eval-llm-demo`: `summary.guarantee_demonstrated == true` with a non-zero
  guard-turn count; record the headline score.
- `make demo-run` completes the scripted scenario live without error.
- **Regression pass clean:** every `[FIXED]`/DONE SEV in `REVIEW_FINDINGS.md` and
  the INDEX carry-forward still has its fix present AND its guard test on disk.
- **No new P1/P2** findings remain open; every new P3 is logged in `ISSUES.md`.

---

## 1. Reviewer lenses (parallel subagents)

Each reviewer is read-only, runs in parallel, and emits findings in the **shared
schema** (§3). Reviewers do NOT fix — they report. Effort budget is high; prefer
false positives surfaced-and-dismissed over missed issues.

### L1 — Security (`security-reviewer`)
Scope: `auth/`, `api/`, `config/`, `engines/` LLM boundaries.
Check: auth on every route except `GET /health` (401 no-body); input caps
(`MAX_PLAYER_MESSAGE_CHARS`, `delta_ticks` bounds); Cypher label/identifier
injection (`cypher_identifier` wrapping everywhere dynamic labels are built);
prompt injection (raw `player_message` / consolidation turns into prompts);
secret handling (no hardcoded keys, env-gated prompt logging
`LOG_LLM_PROMPTS AND ENV==dev`); rate-limit cap + bucket eviction; WS connection
cap; error-envelope redaction (no internal detail leaks). Re-verify SEV-03, -16,
-17, -19, -20, -21, -22 specifically.

### L2 — Architecture / layer integrity (`architect`)
Scope: whole `src/npc_engine/`.
Check: `make check-layers` clean; **no Cypher outside `graph/`** (note: review
flagged remaining raw Cypher in `retrieval/`, `world/`, `scheduler/` — confirm
status); no LLM in `graph/`/`retrieval/`; no prompt strings outside `prompts/`;
DIP (engines import protocols, never concretes; `api/dependencies*.py` is the only
composition root); session ownership (only `graph_writer.py` opens/commits tx);
SRP per module. **Reconcile the `observability/` directory** — it exists in `src/`
but is absent from the CLAUDE.md layer model: either add it to the model (with a
rank + allowed deps) or fold it, via a DECISIONS entry.

### L3 — Type safety / boundaries (`typescript-reviewer` is wrong — use `python-reviewer`)
Scope: `api/` schemas, `type_registry/`, `graph/` writers, engine I/O.
Check: Pydantic v2 for all boundary data (no raw `dict` crossing a module
boundary); `response_model=` on every route; `Literal`/`Enum` for fixed value
sets; mypy 0 sustained (not just ratcheted); `from __future__ import annotations`
+ `TYPE_CHECKING` discipline. Re-verify SEV-14.

### L4 — Test quality & coverage (`python-reviewer` second pass / `tdd-guide`)
Scope: `tests/`, `e2e/`, `evals/`.
Check: coverage ≥ 80% AND meaningful (not asserting on fallbacks/empty — the #1
systemic weakness last time); mocks honor real adapter contracts (LSP — empty
input behavior matches); each `[FIXED]` SEV has a regression/guard test; eval
matchers are strong (min_length, keyword_none on fallback, tone_judge inject);
the 8 pre-existing failures (ISSUE-056) — root-cause each; flakiness (double-run a
sample suite). Re-verify SEV-01, -38, -43.

### L5 — Coding principles & cleanliness (`refactor-cleaner` + manual)
Scope: whole tree.
Check: file-size (≤300 non-test, account for documented DEC waivers); function
length ≤40; nesting ≤3; no magic numbers/strings (named constants / config keys);
docstrings (module/class/public-fn) per `check-docstrings`; naming; **dead code**
(unused exports, orphaned modules, leftover bridge/temp files — CLAUDE.md forbids
orphans); stray `print()`; stray root-level copies of ISSUES/DECISIONS/ROADMAP;
TODO/FIXME debt. Cross-check the 57-entry `rules_baseline` — has it shrunk and
been ratcheted, or are violations accumulating silently?

### L6 — Product / feature completeness (`general-purpose`)
Scope: docs ↔ code ↔ behavior.
Check: every capability the README/docs/pitch promise is actually wired and
reachable: persistent memory, gossip + distortion (2-hop path), emotion + mood
contagion, quest generation + economy atomicity, RAG anti-hallucination guard,
tick scheduler, win/lose game loop (SEV-11 — reachable victory AND defeat), demo
as standalone client (SEV-02 — zero `src/` imports). Flag any promise with no
backing or no test.

### L7 — Expansion readiness (`architect`, second mandate)
Scope: extension seams.
Check (OCP/ISP/DIP for *future* work): can a new LLM backend be added by a new
file only (no edits to existing engines)? a new distortion type? a new emotion
model? a new engine? Are protocols small and single-purpose? Is `type_registry/`
open for new node/edge types without core edits? Is the seeding contract
extensible (ISSUE-055 client-supplied ids)? Is the planned **location hierarchy**
(ISSUE-057, `PART_OF` edges) blocked by any current coupling? Output a ranked list
of the top friction points for the next phase of development.

### L8 — Regression checker (`general-purpose`)
Scope: `REVIEW_FINDINGS.md` `[FIXED]` set + INDEX carry-forward notes.
For each prior fix: confirm (a) the code change is still present, (b) its named
guard test exists on disk and references the right symbol. Produce a table:
SEV-NN | fix-present? | guard-test-present? | notes. Any "no" is a P1 regression.

### L9 — Live verifier (sequential, heavy — runs alongside L1–L8)
Prereq: Docker up + `docker-compose up -d` + `make demo-seed`.
Run and capture full output of: `make check`, `make test`, `make eval-llm-demo`,
`make demo-run`. Save logs to `project-harness/review-evidence/final/`. Report
each as PASS/FAIL with the failing tail. This arm turns "asserted" into "measured".

---

## 2. Phase plan & checkpoints

- **Phase 0 — Env bring-up.** User starts Docker Desktop. Then `docker-compose up -d`,
  `make demo-seed`. Confirm `/health` 200 + Ollama reachable. *(blocks L9 only;
  L1–L8 static lenses can start immediately.)*
- **Phase 1 — Review.** Launch L1–L8 in parallel + L9 live. Consolidate into
  `FINAL_REVIEW_FINDINGS.md` with the §3 schema + a triage table (severity ×
  confidence). **▣ CHECKPOINT: human approves triage & severities before any fix.**
- **Phase 2 — Remediate.** TDD each accepted finding (failing test → fix → green).
  Drive `make check` + `make test` to the §0 bar. **▣ CHECKPOINT: human approves
  the fix diff.**
- **Phase 3 — Features compilation.** Produce `FEATURES.md`: internal engine
  capabilities + external integration surface (HTTP/WS routes, auth, seeding,
  config knobs, fallback contracts). **▣ CHECKPOINT.**
- **Phase 4 — Demo walkthrough.** Run `make demo-run` live, capture transcript,
  write the walkthrough around real output (gossip path, emotion/quest beats, what
  each step proves). Final summary + updated ISSUES/DECISIONS.

## 3. Shared finding schema (every reviewer emits this)

```
FINDING [<lens>-NN]: <one-line title>
Severity: CRITICAL|HIGH|MEDIUM|LOW · Confidence: Confirmed|Likely|Suspected
Category: security|architecture|types|tests|cleanliness|product|expansion
Rule violated: <CLAUDE.md rule or principle>
Location(s): <file:line>
Evidence: <the actual code / command output proving it>
How it manifests: <runtime / product impact>
Root cause: <why>
Blast radius: <what else is affected>
Recommended fix: <concrete steps>
Verification: <how to prove it's fixed>
Effort: S|M|L|XL
```

## 4. Rules of engagement

- Reviewers are **read-only**. Fixes happen only in Phase 2, post-approval.
- Severity is regression-aware: a reintroduced prior fix is **P1** automatically.
- No assumptions: every finding cites file:line or command output as evidence.
- Findings that turn out clean are still listed (as "verified clean") so coverage
  is auditable — mirror the prior review's attestation section.
- New issues not fixed this pass → `ISSUES.md`. New decisions → `DECISIONS.md`.
