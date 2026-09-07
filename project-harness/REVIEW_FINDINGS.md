# NPC Engine — Full Codebase + Demo Review: Consolidated Findings

**Date:** 2026-09-07 · **Branch:** `remediation-2026-08` · **HEAD:** `8d30a3e1`
**Mode:** 10-lens parallel review (engines + demo), 4 concurrent, night run
**Prior review:** `project-harness/review-2026-08/` (145 findings → 118 canonical, 4 CRITICALs) — **not** the
2026-06-03 archive, which is two cycles stale. Both were used as re-verification input.
**Evidence:** `project-harness/review-fixes/evidence/{L1,L2,L4,L6,L7,L9,L10,L11,L12,L13}.md`

**Working tree: CLEAN.** The brief anticipated an in-flight measurement-remediation Phase 5; that work
landed in `ef870f7f` before this run started. `git status --short` was empty at HEAD `8d30a3e1`, so
`--allow-dirty` was moot and no finding is against uncommitted work.

Lenses L3 (types), L5 (cleanliness) and L8 (regression sweep) are retired; their ids are not reused.

---

## 1. Verdict

**The tree is NOT release-clean, and the reason is entirely invisible to the gates.**

`make check` is green end to end — exit 0 in 11m58s, mypy 0 across 637 files, coverage 88.13% / 82.79%,
every ratchet holding. `make test` passes 4,571. `make test-demo` passes 1,116, matching the 2026-08-28
baseline exactly. By every mechanical measure this repo is in good shape, and that is the finding: **all
five CRITICALs are live-only, and none of them is visible to a single gate in `make check`.**

🔴 **The demo is unusable in two independent ways, both confirmed by running it.** A WebSocket slot leak
(`dialogue_ws.py:231-233` — the idle-drain loop only *sends*, so a client close never surfaces as
`WebSocketDisconnect` and `_release_ws_slot` never runs) exhausts the 5-connection cap: `make demo-run`
dies at ACT 6 of 12 with `ws_connection_cap_reached`, and because `game_controller.py` opens a fresh
socket per send, **the interactive demo dies after exactly 5 dialogue turns.** Separately, **an untouched
demo loses itself 3 seconds after seeding** — `battle_resolved … winner iron_legion … tick 5`, zero player
input, on the default 10s autopilot, because the seed co-locates the Iron Legion and City Guard at
`loc_guard_barracks` and that pair is exactly `DEMO_LOSE_LOCATION_ID`/`FACTION_ID`. Win is unreachable;
lose is the default outcome. A studio evaluator loses the demo before touching it.

🔴 **Nothing protects the single resident model from the tick loop.** There is no queue, no priority and
no admission control in front of it; the one declared defence, `TICK_LLM_CALLS_PER_MINUTE_MAX`, is broken
on three independent axes (it counts *ticks* not calls, gates 2 of 5 LLM engines, and is never passed at
all in the *recommended* `game_driven` clock mode). Worst-case tick: ~84 model calls, independently
derived by two lenses. A player's dialogue turn arriving mid-tick either lands tens of seconds late or
degrades to `canned`.

Beneath the CRITICALs, the engine portfolio is far emptier than it looks: **17 of 27 engines did no work
across six live tick advances**, two of them provably dead because the seed never writes the edges they
query. And `make check`'s green is narrower than it reads — it executes zero real Cypher.

**Nothing here is a mechanical regression** in the sense the prior reviews measured. Every re-verified
prior fix holds. The failures are in the space between the gates.

---

## 2. Severity counts

| Severity | Count | IDs |
|----------|------:|-----|
| 🔴 CRITICAL | 5 | L9-01, L6-01≡L9-02, L11-03, L13-05, L13-06 |
| HIGH | 17 | L1-01, L2-02, L4-01, L4-02, L4-03, L9-03, L9-04, L11-02, L12-02, L12-11, L12-12, L12-14, L13-01, L13-02, L13-04, L13-07, L13-09 |
| MEDIUM | 27 | L1-02, L2-01≡L7-05, L2-03, L2-04, L4-04, L4-05, L6-02, L6-03, L7-01, L7-03, L9-05, L9-06, L10-01, L10-02, L10-03, L11-01, L11-04, L11-05, L12-01, L12-04, L12-05, L12-07, L12-08, L12-09, L13-03≡L10-04, L13-08, L13-10 |
| LOW | 16 | L1-03, L1-04, L2-05, L2-06, L4-06, L7-02, L7-04, L7-06, L9-07, L9-08, L9-09, L12-03, L12-06, L12-10, L12-15, L12-18 |
| Informational | 3 | L12-13, L12-16, L12-17 |
| **Total** | **68** | (65 defects + 3 informational; 4 cross-lens duplicate pairs merged) |

Cross-lens merges: **L6-01 ≡ L9-02** (auto-lose: traced statically, then confirmed live),
**L2-01 ≡ L7-05** (`TraitReadPort` dead, DIP framing and OCP framing),
**L10-04 ≡ L13-03** (stale `military` docstring), and L11-03 / L13-05 / L13-06 are three distinct
defects in one mechanism (model contention) rather than duplicates.

---

## 3. Systemic patterns

Leading with the clusters that shrink what the model must do — the standing goal.

### 3.1 🔴 Nothing arbitrates the single resident model (L11, L13) — *the small-model cluster*
This is the review's most important finding and it spans two lenses that reached it independently.
One Ollama process holds one model. Against it: an interactive dialogue turn on a 3–7s budget, and a tick
loop that can issue **~84 model calls** (L13 derived 64 sequential + up to 20 concurrent from shipped
caps; L11 counted ~86 from the retry loops — 40 from event triggers, 40 from need triggers, neither
covered by the `skip_llm_engines` load-shed switch, which gates only `chapter` and `memory_consolidation`).
Costed against measured decode rates that is **84–220 seconds of model time in one tick**. There is no
semaphore, lock, queue or priority anywhere in `engines/llm/`. `LLM_TIMEOUT_SECONDS=60`, so a player's
turn arriving mid-tick lands very late or silently degrades to `canned`.

The one declared defence is broken on every axis: `TICK_LLM_CALLS_PER_MINUTE_MAX` counts ticks rather
than calls, applies to 2 of 5 LLM engines, and `advance_clock` never sets `skip_llm_engines` at all — so
in the *recommended* clock mode the cap does not exist. **DEC-273's 3.5–4.2s warm dialogue is an
idle-backend best case that no real session reproduces.**

Worse, the biggest measured stall is not LLM at all: **the gossip tick cost 24.25s wall-clock with zero
model calls** (surrounding ticks: 433–570ms), because `refresh_embedding_safely` runs a full corpus
reconciliation *per propagated pair* inside a serial loop — 10 passes in one tick, on the same GPU as the
resident model, and no LLM budget would ever shed it.

**Implication for the small-model goal:** model *size* is not the current constraint — *contention* is.
Swapping to a 3B without admission control just makes 84 fast calls collide with one interactive turn
instead of 84 slow ones. Admission control is the prerequisite for the model swap, not a follow-up to it.

### 3.2 The engine portfolio is mostly inert, and the observability cannot say so (L10, L13)
Across six live tick advances, **27 engines ran, 0 reported errors, and only 6 did any work.** 17 reported
zero effect. Two have identified root causes, both graph-shape defects that no observable can express:
`routine` can never move an NPC because the seed writes no `:Schedule` node or `FOLLOWS_SCHEDULE` edge at
all — which then starves `mood_contagion`, `proactive_dialogue`, `player_model` and `need_decay`'s
satisfier join; and 28 `:Need` nodes are orphans (the seed writes a `character_id` *property* but never
the `HAS_NEED` edge), killing `need_decay` and `need_quest_trigger` outright.

`engine_status` is exposed on two endpoints, **read by nothing**, and structurally cannot distinguish
"ran and correctly did nothing" from "starved and silently dead" — every `last_error` was null while a
third of the portfolio was inert. Separately L10 found 7 delete-candidate engines, 2 fully dead classes
(`DeceptionEngine`, `SchemingEngine`), one vaporware engine shipping its own contract *and* a passing
contract test (`currency`), 9 dead `Settings` fields and 2 dead prompt YAMLs.

Every inert engine is surface area a model, a prompt, a context assembler and a maintainer all pay for.
This cluster is the "what can we delete" input, and it is large.

### 3.3 The prompt was never read as a prompt (L12)
4,245 static tokens of 17 rules on every turn, reviewed for hygiene by three prior cycles and for
*content* by none. Result: two conflicting rule pairs, two redundant clusters (Rules 2/16 implement the
same 5-band tone system from different data; Rules 5/14/17 restate one anti-hallucination policy three
times), one rule instructing the model to read a field no producer emits, **two rules both numbered 17**,
and Rule 15 out of sequence — evidence the assembled artifact was never proofread as one document.

The schema side is worse: the prompt instructs **4 of 13** response fields. Of the 6 the model actually
generates, `facial_expression` and `mood_update` get *zero* guidance and `relation_deltas.fear` is
silently omitted — and `facial_expression` is player-visible in `demo_game/` and judged by evals.
`max_tokens: 512` gives 3–4× headroom over the "1–3 sentences" the prompt requests, with nothing
structurally capping `npc_response`. Since decode dominates and scales with output tokens, that is a real
latency lever — and unusually, **fixing it is free**: it touches `llm_config.yaml` and `dialogue_models.py`,
not the prompt, so `dialogue_prompt_hash` is unchanged and eval comparability survives.

L12 also found the constraint itself is mis-specified: `dialogue_prompt_hash` hashes the **entire**
`prompts/` tree, not just the dialogue prompt — so editing an unrelated prompt already breaks
comparability, and the caution everyone has been observing is both too broad and too narrow.

### 3.4 The gates are green over a narrower surface than they appear to cover (L4, L9, L13)
The 2026-06-03 review named "asserted-not-measured" as its #1 pattern. It persists, relocated. `make check`
is green and **executes zero real Cypher** — 40 of 51 integration tests skip locally. Auth-middleware
wiring on the production `create_app()` has no end-to-end test; only a hand-built app proves 401. The WS
connection cap is tested at the helper, not the endpoint — which is precisely where the CRITICAL leak
lives. `arm_probe.py`, the P9 *measurement-integrity* tool, ships at 0% coverage. No test pins tick
execution order, so every read-after-write dependency between engines can be broken silently. And the
only gate on the scripted demo is `--dry-run`, which makes no API calls — which is why a demo that dies
at ACT 6 and loses itself in 3 seconds passed every check.

### 3.5 Abstraction the codebase does not use (L2, L7, L10)
**34 of 44 Protocols (77%) fail the repo's own "2+ implementors or 3+ callers" rule** — most have exactly
one implementor and one caller. ~30 files of pure indirection, ~170 Protocol methods, 39 matching
repository classes, for polymorphism never exercised. Two are god-ports (9 and 11 methods, one caller).
`TraitReadPort` has *zero* implementors: DEC-137's "slice-2" never landed in 2.5 months, so
`TraitModulatedEmotionModel` is unreachable and every NPC silently gets the shared fallback model.
Meanwhile the seams the roadmap actually needs are closed — adding a tick engine edits 4 existing files.
Abstraction is concentrated where it is not needed and absent where it is.

### 3.6 Documentation asserts capability the code does not have (L7, L10, L12, L13, L9)
A recurring, cheap-to-fix shape: `factory.py` docstrings describe a self-registration pattern the code
does not use; `distortion_strategy.py`'s `registry_keys()` overclaims openness; `tick_scheduler.py` calls
`military` a no-op stub while it resolves a battle every tick (and cites an unrelated resolved issue);
ISSUE-107 claims a scenario is "wired into the e2e battery" when nothing collects it; ISSUE-273 is fixed
but still open. **And DEC-273 — three days old — is contradicted on 3 of 5 measured claims by this run.**

### 3.7 DEC-273's mechanism holds; its constants do not (L9)
Re-measured live over 4 turns: decode is **68.7 / 87.4 / 84.4%** of a warm turn, not ~97%. Prefill is
**540–1,779ms**, i.e. 11–30% of the turn, not "prefix-cached and effectively free". Warm dialogue is
**4.79–5.95s** backend / 5.26–6.39s end-to-end, not 3.5–4.2s — still inside the 3–7s budget, but with far
less headroom than recorded. Confirmed: the 10.3s cold load (10.515s) and that `keep_alive` holds the
model (`load_duration_ms` 10,515 → 7.9/10.3/10.1ms; `/api/ps` showed the model resident with 29.5 min
left). **Half-true:** `keep_alive` prevents the *second* cold load, not the *first* — there is no startup
warm-up, so the demo's opening line costs **20.1s end-to-end**. DEC-273 needs amending, not retracting.

---

## 4. Triage table

Disposition: **Fix now** (in the backlog) · **Log** (→ ISSUES.md) · **Decide** (needs your call).
Per invariant, nothing graded *Suspected* is dispositioned Fix-now.

| ID | Sev | Title | Lens | Disposition |
|----|-----|-------|------|-------------|
| L9-01 | 🔴CRIT | WS slot leak — demo dies at ACT 6; interactive UI dies after 5 turns | live | **Fix now** SEV-01 |
| L13-05 | 🔴CRIT | `TICK_LLM_CALLS_PER_MINUTE_MAX` counts ticks, gates 2/5 engines, absent in recommended mode | runtime | **Fix now** SEV-02 |
| L11-03 | 🔴CRIT | Quest triggers multiply to 40+ sequential model calls/tick, uncapped across 3 engines | llm | **Fix now** SEV-03 |
| L13-06 | 🔴CRIT | No queue/priority/admission control in front of the single resident model | runtime | **Fix now** SEV-04 |
| L6-01≡L9-02 | 🔴CRIT | Untouched demo reaches LOSE 3s after seeding; win unreachable | demo+live | **Decide** (fix shape) |
| L9-04 | HIGH | First load is 20.1s — `keep_alive` fixes the 2nd cold load, not the 1st; no warm-up | live | **Fix now** SEV-05 |
| L12-12 | HIGH | `max_tokens: 512` vs "1–3 sentences"; no structural cap on `npc_response` | prompt | **Fix now** SEV-06 |
| L13-07 | HIGH | Gossip tick costs 24.25s — full corpus reconciliation per propagated pair | runtime | **Fix now** SEV-07 |
| L13-09 | HIGH | `delta_ticks: 1000` runs 27 engines 1000× in one request, one lock, stale snapshot | runtime | **Fix now** SEV-08 |
| L1-01 | HIGH | `/ws/dialogue` has no throughput rate limit; middleware structurally can't see WS | sec | **Fix now** SEV-09 |
| L11-02 | HIGH | Per-engine declared timeouts are dead config for 4 of 5 engines | llm | **Fix now** SEV-10 |
| L4-02 | HIGH | Auth wiring on production `create_app()` has no regression test | tests | **Fix now** SEV-11 |
| L13-04 | HIGH | `engine_status` read by nothing; cannot express "starved" | runtime | **Fix now** SEV-12 |
| L9-03 | HIGH | DEC-273's latency constants contradicted on 3 of 5 claims | live | **Fix now** SEV-13 |
| L4-01 | HIGH | `arm_probe.py` / `arm_probe_report.py` — the measurement-integrity tool — at 0% coverage | tests | **Fix now** SEV-14 |
| L13-10 | MED | No test pins tick execution order — every read-after-write dep breakable silently | runtime | **Fix now** SEV-15 |
| L13-01 | HIGH | Seed writes no `:Schedule`/`FOLLOWS_SCHEDULE`; `routine` dead, 4 engines starved | runtime | **Decide** (seed data) |
| L13-02 | HIGH | 28 orphan `:Need` nodes, no `HAS_NEED` edge; 2 engines dead | runtime | **Decide** (seed data) |
| L2-02 | HIGH | 34/44 ports (77%) fail the repo's own DIP threshold | arch | **Decide** (interface) |
| L12-11 | HIGH | `facial_expression`/`mood_update` generated with zero prompt guidance | prompt | **Decide** (hash cost) |
| L12-14 | HIGH | `dialogue_prompt_hash` hashes the whole `prompts/` tree, not just dialogue | prompt | **Decide** (eval semantics) |
| L12-02 | HIGH | Rule 8 (VOICE) vs Rule 2 (ALLIED band) conflict for guard/soldier archetypes | prompt | **Decide** (hash cost) |
| L4-03 | HIGH | `make check` executes zero real Cypher; 40/51 integration tests skip locally | tests | **Decide** (CI gating) |
| L10-01 | MED | `currency` is vaporware with its own contract *and* a passing contract test | portfolio | **Decide** (delete set) |
| L10-02 | MED | `DeceptionEngine`/`SchemingEngine` are dead classes | portfolio | **Decide** (delete set) |
| L10-03 | MED | 5 of 7 political engines invisible to the API — parallel graph-service layer | portfolio | **Decide** (canonical path) |
| L2-01≡L7-05 | MED | `TraitReadPort` zero implementors; DEC-137 slice-2 never landed | arch+ocp | **Decide** (impl or delete) |
| L9-08 | LOW | Only gate on the scripted demo is `--dry-run`, which makes no API calls | live | **Decide** (DEC-224) |
| L1-02 | MED | `API_KEY_GRAPH_WRITE`/`_ADMIN` have no weak-secret validation | sec | **Log** |
| L2-03 | MED | Two god-ports (9 and 11 methods) with a single caller | arch | **Log** |
| L2-04 | MED | Ports import graph-owned types, one an explicitly private Protocol | arch | **Log** |
| L4-04 | MED | WS cap tested at helper, not endpoint (where the CRITICAL lives) | tests | **Log** |
| L4-05 | MED | Repository-passthrough / Cypher-substring tests asserted-not-measured | tests | **Log** |
| L6-02 | MED | ISSUE-107's "wired into the e2e battery" is false — nothing collects it | demo | **Log** |
| L6-03 | MED | Entire branch system is one two-option stub, undocumented as final scope | demo | **Log** |
| L7-01 | MED | `matchers.py` `_DISPATCH` is a closed seam for new scorer kinds | ocp | **Log** |
| L7-03 | MED | Adding a tick engine requires editing 4 existing files | ocp | **Log** |
| L9-05 | MED | `llm_tokens_in_total` excludes the system channel — under-counts 4.3× | live | **Log** |
| L9-06 | MED | Latency instrumentation cannot express the budget it defends (no buckets) | live | **Log** |
| L11-01 | MED | `stream`/`stream_text` call site dead in the production dialogue path | llm | **Log** |
| L11-04 | MED | Memory consolidation asks for JSON via the unstructured `generate` | llm | **Log** |
| L11-05 | MED | Proactive dialogue has zero fallback and no timeout enforcement | llm | **Log** |
| L12-01 | MED | Two rules numbered 17; Rule 15 out of sequence | prompt | **Log** |
| L12-04 | MED | Rule 16 vs Rule 2 tie-break delegated to model "judgement", no algorithm | prompt | **Log** |
| L12-05 | MED | Two independent 5-band tone systems doing the same job | prompt | **Log** |
| L12-07 | MED | Output-rules prose restates schema-enforced constraints | prompt | **Log** |
| L12-08 | MED | Rule 11 reads `available_interactions`, which no producer emits | prompt | **Known** ISSUE-293 |
| L12-09 | MED | 5 of 18 context slots read by no prompt rule | prompt | **Known** ISSUE-292 |
| L13-03≡L10-04 | MED | `military` reports `battles_resolved: 1` every tick; docstring calls it a no-op | runtime | **Log** |
| L13-08 | MED | Two unlogged unbounded appenders: `:TickLease`, `SchedulerState` array | runtime | **Log** |
| L1-03 | LOW | Admin `npc_ids`/`location_ids` lists unbounded | sec | **Log** |
| L1-04 | LOW | `is_public_path` prefix-matches `/setup` (Suspected) | sec | **Log** |
| L2-05 | LOW | Three quest Protocols redeclare identical methods | arch | **Log** |
| L2-06 | LOW | CLAUDE.md layer diagram omits `observability/` and `setup/` | arch | **Log** |
| L4-06 | LOW | Existence-only tests (`hasattr`) assert wiring, not behaviour | tests | **Log** |
| L7-02 | LOW | `factory.py` docstrings describe a self-registration the code doesn't use | ocp | **Log** |
| L7-04 | LOW | Location-connection `kind` still unconstrained `str` | ocp | **Log** |
| L7-06 | LOW | `distortion_strategy.registry_keys()` docstring overclaims | ocp | **Log** |
| L9-07 | LOW | `check-rules` reports a resolved baseline entry, never ratchets down | live | **Log** |
| L9-09 | LOW | `BASELINE_2026-08-28.md` no longer matches the tree | live | **Log** |
| L12-03 | LOW | Rule 9 vs Rule 5 collide on a true player claim (Suspected) | prompt | **Log** |
| L12-06 | LOW | Three rules restate one anti-hallucination policy | prompt | **Log** |
| L12-10 | LOW | Rule 8 carve-out plausibly contributes to ISSUE-128 (Suspected) | prompt | **Log** |
| L12-15 | LOW | `slot_fill_v1.yaml`/`flavor_v1.yaml` dead; config still names dead `v1` | prompt | **Log** |
| L12-18 | LOW | `tone_judge.yaml` construction assessment | prompt | **Log** |

---

## 5. Already known

Checked against `ISSUES.md` (117 open), `archive/ISSUES_RESOLVED.md` (180) and
`review-2026-08/{FINDINGS,TRIAGE}.md` (118 canonical).

| Finding | Known as | Status on this tree |
|---|---|---|
| L12-08 | ISSUE-293 | Unchanged — re-verified live, dropped from backlog |
| L12-09 | ISSUE-292 | Unchanged — re-verified live, dropped from backlog |
| L12-16 | ISSUE-223 | Unchanged (prompt singleton, no A/B) — confirmation only |
| L4-05 | CR-L14-02 | Delegate-test pattern verbatim unchanged; CI-side gap now partly closed |
| L4-06 | ISSUE-132 | Same defect class, already tracked |
| L13-08 | ISSUE-279 | *Related, not duplicate* — different nodes, same retention gap → new issue |
| L13-02 | ISSUE-210 / ISSUE-213 | **PROMOTED** — logged as cosmetic (empty prompt field); actually two dead engines |
| L11-02 | ISSUE-298 | Adjacent (that is temperature, this is timeouts) — logged separately |
| L4-03 | ISSUE-274 | ISSUE-274 is the symptom; L4-03 is the mechanism |

**Ledger corrections found (not new defects):**
- **ISSUE-273 is fixed but still open** — the `has_draft_quest` guard exists at
  `world_state_quest_trigger.py:150`; `:Quest` held at 18 across 6 advances. Should be archived.
- **The 2026-06-03 L1-05 finding (prompt injection unmitigated) is FIXED** — fencing now exists and is
  substantive (L12-13). It should not be re-flagged by future reviews.
- **ISSUE-210's severity is wrong** (P2/cosmetic → two dead engines). Re-scoping touches seed data.

**Regressions:** one. **L6-01 ≡ L9-02 contradicts the 2026-06-03 §4 attestation "SEV-11 — win AND lose
reachable."** L9 judges this an original asserted-not-measured miss rather than a code regression —
nothing indicates it ever worked — but the attestation was false when written and is false now, so it is
promoted, not dropped. Every other re-verified prior fix HOLDS; no previously-fixed claim is now broken.

---

## 6. Confidence ledger

| Grade | Count | Notes |
|---|---:|---|
| Confirmed | 60 | Includes all 5 CRITICALs; 2 of them observed running, not inferred |
| Likely | 2 | L12-02 (rule conflict), L13-03 (`military` per-tick battle) |
| Suspected | 3 | L1-04, L12-03, L12-10 — **all dispositioned Log**, none Fix-now |
| Informational | 3 | L12-13, L12-16, L12-17 — confirmations, not defects |

Invariant satisfied: no *Suspected* finding is in the Fix-now backlog.

**Method note.** Two CRITICALs (L9-01, L9-02) were found only by running the system — `make demo-run` live
and a booted stack with the autopilot left alone. Two more (L11-03, L13-05/06) came from tracing call
sites and costing them out, not from reading tests. The lens that ran things found what nine lenses of
reading could not, which is the same lesson as the 2026-06-03 cycle.

---

## 7. What this review did not cover

- **Judged eval quality.** All five scorers are REFUSED by `scripts/check_label_adequacy.py` and the label
  set is not frozen, so no lens quoted a judged score. Whether open-generation quality would survive a 3B
  is therefore **unmeasurable today** — L11's verdict says so explicitly. Fixing the scorer layer is the
  prerequisite for answering the model-size question on quality grounds.
- **Integration tests were not run** — they write to the live Neo4j (ISSUE-277). L4's conclusions about
  real-Cypher coverage are from reading the skip behaviour, not from executing the suite.
- **Load beyond a single session.** All latency figures are single-player, single-session.
