# Issues Log

Persistent issues log. Read at the start of every session. Updated whenever
work is deferred or completed.

Rules:
- Never reuse IDs (check both this file and the archive for the next id).
- Never delete entries. When fixed, mark `[FIXED]` with a `**Fixed:**` line, then
  move the entry to [`archive/ISSUES_RESOLVED.md`](archive/ISSUES_RESOLVED.md).
- Severity: P1 (blocking) | P2 (annoying) | P3 (nice-to-fix).
- New issues get the next monotonic ID.

> **Resolved issues are archived.** Closed/fixed entries now live in [`archive/ISSUES_RESOLVED.md`](archive/ISSUES_RESOLVED.md). This file tracks open issues only.

---


## ISSUE-094: proactive trigger_router has no `need`/`event` candidate producers
**Found:** 2026-06-12, during F1.2 (proactive WS delivery wiring)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/proactive_dialogue/proactive_tick_adapter.py` (`_collect_candidates`)
**Description:** `trigger_router.select_trigger` is now wired, but only the `memory` source emits
`TriggerCandidate`s. `TriggerSource` also defines `need` and `event` — those producers don't exist,
so routing is effectively single-source today.
**Why deferred:** Out of F1.2 scope; building need/event producers is its own slice and the router is a
clean seam for them. Deferring avoided scope creep in the overnight loop.
**To fix:** Add need-based (IntentFormationEngine) and event-based candidate producers that append
`TriggerCandidate(source="need"|"event", ...)` in `_collect_candidates`; the router already ranks them.

---

## ISSUE-095: dialogue_ws lazily imports get_proactive_queue inside the handler
**Found:** 2026-06-12, during F1.2
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/api/routes/dialogue_ws.py` (`dialogue_ws` body)
**Description:** `get_proactive_queue` is imported inside the WS handler function to avoid a potential
import cycle at module load.
**Why deferred:** Works correctly; promoting to a top-level import is cosmetic and needs the
api/dependencies_engines import graph confirmed acyclic first.
**To fix:** Verify no circular import, then hoist the import to module top-level.

---

## ISSUE-096: trait-modulated emotion uses global demo-default traits, not per-NPC traits
**Found:** 2026-06-12, during F1.3 (config-selectable emotion model)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/emotion/emotion_model_factory.py` (`_DEMO_DEFAULT_TRAITS`)
**Description:** When `EMOTION_MODEL="trait_modulated"`, `EmotionUpdater` holds ONE model seeded with
global demo-default trait multipliers, so every NPC is modulated identically. `TraitModulatedEmotionModel`
is designed for per-NPC traits (its docstring: "caller responsible for fetching traits from the graph").
**Why deferred:** F1.3 scope is the config selector + composition-root injection; per-NPC trait fetch is
its own slice (needs a graph traits reader + an EmotionUpdater call-signature change to thread npc traits).
**To fix:** Add a per-NPC traits reader; have `EmotionUpdater` build/parameterize the model per `npc_id`
(or pass traits into `apply_shock`/`apply_mood_hint`), removing the global default.

---

## ISSUE-097: director plateau-tick signal is always 0 (no relationship-plateau tracker)
**Found:** 2026-06-12, during F1.5 (director → scheduler)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/director/director_tick.py` (`_decide_for_pair`)
**Description:** `DirectorTick` always passes `relationship_plateau_ticks=0` to `decide()`, so the
`relationship_catalyst` plateau beat can never fire. Only the idle (`re_engage_idle`) and HOSTILE
(`tension_escalation`) paths are live.
**Why deferred:** F1.5 scope is the decide→emit wiring; tracking ticks-since-Standing-band-changed
needs a small per-pair tracker/store, its own slice.
**To fix:** Track consecutive ticks since the pair's Standing band last changed (a per-pair counter,
e.g. on the RELATES_TO edge or an in-memory store) and feed it into `decide()`.

---

## ISSUE-098: composition root builds a fresh PlayerLocationReader per factory
**Found:** 2026-06-12, during F1.5
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/api/dependencies_engines.py` (proactive/intent/player_model/director factories)
**Description:** Four `@lru_cache` factories each construct their own `PlayerLocationReader()`. It is
stateless so this is functionally fine, but a shared `get_player_location_reader()` singleton would be
more consistent with the rest of the composition root.
**Why deferred:** Cosmetic; not blocking. Surfaced by the F1.5 worker.
**To fix:** Add `@lru_cache get_player_location_reader()` and reuse it across the four factories.

---

## ISSUE-100: `make demo-run ARGS=--dry-run` fails partway (pre-existing, ~ACT 8)
**Found:** 2026-06-12, during G3.1 (verifying the intrigue arc in the demo sequence)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/run.py` SCENES / `make demo-run` dry-run path
**Description:** `make demo-run ARGS=--dry-run` (meant to print the scene sequence only) exits with error
partway through (around the ACT 8/determinism region) — confirmed PRE-EXISTING (reproduces with G3.1
changes stashed). Individual scenes respect `runner.dry_run`; the failure is elsewhere in the dry-run
harness/sequence, not the new intrigue scenes.
**Why deferred:** Out of G3.1 scope (G3.1 adds the intrigue scenes, which are unit-tested and respect
dry_run); the dry-run harness bug predates this work.
**To fix:** Bisect which scene/step errors under `--dry-run` and make the dry-run path fully non-networked
end-to-end.

---

## Open

---

## ISSUE-083: two voice tone_judge cases fail under epoch=war / stage_b_v2.9 (captain_sorn, mira_innkeeper)
**Found:** 2026-06-09, during eval re-run
**Severity:** P3 (nice-to-fix — voice quality, not anti-hallucination)
**Where:** `case_voice_captain_sorn_001`, `case_voice_mira_innkeeper_001`; possibly influenced by
the `ECHO_GUARD` line in `prompt_builder.py` (stage_b_v2.9).
**Description:** captain_sorn's reply hedges ("no major breakthroughs or setbacks announced yet"),
failing the authoritative-military voice judge (borderline, pre-existing). mira_innkeeper's reply
reads as a dry objective war report rather than warm gossip ("Villagers speak of soldiers
marching...") and now fails the warm-gossip voice judge — it was passing before. The new ECHO_GUARD
("answer only in your own general terms... speak only from the knowledge in your context") may be
nudging NPCs toward terse, factual reporting at the cost of voice colour; could also be LLM variance.
**Why deferred:** Voice polish is a separate axis from the anti-hallucination guarantee this task targets.
**To fix:** Confirm whether ECHO_GUARD is the cause (A/B a couple of runs with the line removed). If
so, soften the guard wording so it constrains echoing without flattening voice, or scope it to only
fire when the player message contains a planted figure/presupposition. Otherwise tune the two voice prompts.
**Update (2026-06-11, S25.1 / DEC-096):** ECHO_GUARD confirmed as *a* cause and softened in
`prompt_builder.py` (`_ECHO_GUARD_TEXT`, `stage_b_v2.13`): dropped the always-on "answer only in your own
general terms" flattener, scoped each directive to an explicit player plant. Live A/B: voice **0/2 → ~1/2**
(mira recovers gossip framing; captain still borderline-fails on "Reports…/our scouts keep us informed"),
anti-hallucination **5/5** guards still pass (no moat regression). **Kept OPEN — narrowed residual:** the
captain_sorn failure is now voice-judge strictness + a secondary-source ("reports/scouts") habit, not the
ECHO_GUARD. Remaining fix is voice-prompt/seed tuning (out of S25.1's prompt-wording scope) — e.g. a
VOICE_DESCRIPTOR nudge away from third-person reporting toward first-person command, or relaxing the
captain tone judge to accept "reports of skirmishes" as a commander relaying field intel.

---

## ISSUE-053: 57 grandfathered CLAUDE.md rule violations (file-size, swallows, prints, Cypher-leak, demo imports)
**Found:** 2026-06-03, during the multi-agent codebase review
**Severity:** P2 (annoying)
**Where:** `scripts/rules_baseline.txt` (enumerated); spans `src/` and `demo_game/`. Maps to SEV-23 (file-size), SEV-18/PY-06 (swallows), SEV-40 (prints), SEV-04 (Cypher outside `graph/`), SEV-02/DEMO-01 (demo imports `npc_engine`).
**Description:** The `make check-rules` gate (`scripts/check_rules.py`) records 57 existing rule violations as a baseline so only NEW ones fail CI. The baseline is the debt backlog.
**Why deferred:** Each cluster has its own remediation brief in `project-harness/review-fixes/`; the gate prevents growth while they are worked down.
**To fix:** Work the SEV briefs; after each, run `make check-rules-update` to shrink `scripts/rules_baseline.txt`. Done when the baseline is empty.

---

## [WONTFIX] ISSUE-051: Dashboard S12.4 engine cadence/cost controls are read-only (no live mutation)
**Found:** 2026-06-03, during S12.4
**Severity:** P3 (nice-to-fix)
**Where:** `dashboard/js/engines.js`, `src/npc_engine/api/routes/system.py` (`/v1/system/config`)
**Description:** The Engines tab displays runtime cadence/cost config + per-engine status but cannot change them. `Settings` is a frozen `lru_cache` singleton and the autopilot captures `interval_seconds`/`budget_guard` at construction in the lifespan, so there is no runtime-mutation path. See DEC-054.
**Why deferred:** Live mutation requires a `RuntimeConfigStore` injected into the autopilot + a guarded write endpoint — a public-interface/scheduler change needing approval, out of scope for the read-only first slice.
**To fix:** Add a `RuntimeConfigStore` read by the autopilot each loop for interval + LLM budget; expose `PATCH /v1/system/config` (graph_admin scope, bounded values); wire the dashboard inputs to it.
**Closed:** 2026-06-03, S13.2 dropped (DEC-055) — deprioritized below the CRITICAL/HIGH review-remediation backlog; dashboard controls remain read-only. Reopen if a customer needs live tuning.

---

## Closed

---

## ISSUE-071: Dialogue engine not grounded in live engine state — NPC contradicts trade/quest reality
**Found:** 2026-06-05, during trade-engine bug fix (Mira hardcoded item)
**Severity:** P2 (annoying — breaks immersion, confuses players)
**Where:** `src/npc_engine/engines/dialogue/` + `src/npc_engine/retrieval/context_builder.py`
**Description:** The dialogue engine generates NPC responses from graph context alone; it has no awareness of live engine state from other engines (trade, quest, economy). Example: after the trade engine determines that Mira has no inventory and cannot trade, Mira's LLM-generated dialogue still says "I've got a couple of things that might interest you" — because the prompt context only includes graph facts, not the trade engine's real-time evaluation. The same class of bug can occur with quest state (NPC says "bring me the item" after quest is already complete) and emotion state.
**Why deferred:** Requires a design decision on how to pass engine-resolved facts into the dialogue context assembly pipeline without creating layer violations (dialogue engine calling trade engine, or context_builder calling both). Involves a new "system state" tier in the prompt context.
**To fix:** Introduce a `SystemStateContext` bag — a dict of engine-resolved facts assembled at the API route layer before the dialogue call — and inject it as a new Tier 0 block in `context_builder.py`. The route handler (`api/routes/dialogue.py`) would resolve trade/quest state for the current NPC and player, then pass it into the context builder. This keeps layer boundaries clean (engines do not call each other; the route layer orchestrates).

<!--
Template for a new issue:

---

## ISSUE-NNN: <short title>
**Found:** YYYY-MM-DD, during <task>
**Severity:** P1 | P2 | P3
**Where:** <file:line or component>
**Description:** What is wrong.
**Why deferred:** Why this is not being fixed now.
**To fix:** What needs to happen to fix it.

When fixed, change the heading to:

---

## ISSUE-085: `world_state.py` uses deprecated `datetime.utcnow()` (Python 3.12+)
**Found:** 2026-06-09, during EXP-21 (W3)
**Severity:** P3 (nice-to-fix — deprecation warning only, not an error)
**Where:** `src/npc_engine/world/world_state.py` (grep `utcnow`)
**Description:** `datetime.utcnow()` is deprecated in Python 3.12 and triggers warnings in every test run. Replace with `datetime.now(timezone.utc)`.
**Why deferred:** Out of scope for EXP-21; affects test noise only.
**To fix:** `s/datetime.utcnow()/datetime.now(timezone.utc)/g` and add `from datetime import timezone` import.

---

## ISSUE-092: Redis-backed emotion (and other high-churn) store — deferred to Unity/Unreal phase
**Found:** 2026-06-10, during EXP-14 DECISIONS (DEC-084)
**Severity:** P3 (nice-to-fix — Neo4j write-through is sufficient for now)
**Where:** `src/npc_engine/engines/emotion/emotion_store.py` + any future high-churn in-memory store
**Description:** README "What's next" advertises Redis-backed emotion store. Per DEC-084 we are
using Neo4j write-through for EXP-14 slice-1. Under heavy concurrent dialogue Redis would
outperform Neo4j for sub-millisecond hot state (valence/arousal); similarly, session_store and
any tick-rate counters would benefit from Redis TTL semantics.
**Why deferred:** New infrastructure dependency (redis-py / aioredis + Docker service + config).
Blocked until the Unity/Unreal SDK integration phase, which already introduces infrastructure
changes and is a natural inflection point.
**To fix:** Add Redis adapter behind EmotionStore and SessionStore interfaces; register as a
new DI option in `api/dependency_singletons.py`; add Docker Compose Redis service.

---


## ISSUE-104: OCP residuals — emotion/TTS factory, mood-label table, llm `__init__` registration, scheme step kind
**Found:** 2026-06-13, during /full-review (L7)
**Severity:** P3 (nice-to-fix)
**Where:** `engines/.../emotion_model_factory.py`, `dependencies.py` (TTS), `engines/.../mood_contagion_engine.py`, `engines/llm/__init__.py`, `engines/scheming/covert_event_factory.py`
**Description:** Several extension axes remain closed: emotion-model factory is a 2-branch if + Literal;
TTS backend selection is an if/elif in the composition root with no registry; mood label→VAD table is a
hardcoded dict duplicated across two modules; new LLM backends require editing `llm/__init__.py`; scheme
step kind is a free string with no enum/registry. The big OCP seams (distortion registry, location_writer,
LLM backend validator, EmotionModelProtocol) DID land — these are the residuals.
**Why deferred:** Roadmap pre-work, not blocking; each is added when its expansion axis is actually exercised.
**To fix:** Mirror the LLM `register_backend()` registry pattern for emotion + TTS; extract the mood table
to one module; introduce a `SchemeStepKind`.

---

## ISSUE-105: `dependencies_engines.py` exceeds its DEC-076 400-line growth cap
**Found:** 2026-06-13, during /full-review (L2)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/api/dependencies_engines.py` (~513 lines)
**Description:** DEC-076 (2026-06-09) capped the file at 400 lines pending a per-engine submodule pattern;
scheme + director + memory + goal factories pushed it past without a new DECISIONS entry.
**Why deferred:** Composition-root refactor; not blocking. Relates to DEC-115 (second composition root).
**To fix:** Extract advanced engine factories into a submodule, or add a DECISIONS entry re-baselining the cap.
**Progress:** 2026-06-15 (SEV-17) — per-engine submodule pattern established by splitting the *sibling* root
`dependencies_advanced.py` into `dependencies_advanced/{politics,social,progression}.py`. `dependencies_engines.py`
itself is still 512 lines (DEC-076-grandfathered); apply the same split or re-baseline to close this. STILL OPEN.

---

## ISSUE-107: No cross-session e2e test for persistent memory recall
**Found:** 2026-06-13, during /full-review (L6)
**Severity:** P2 (annoying)
**Where:** `e2e/` / demo scenarios
**Description:** The persistent-memory pitch has no e2e scenario spanning two dialogue sessions across a
memory consolidation (teach an NPC something in session 1, confirm recall in session 2). Unit tests cover
the pieces; the headline capability has no end-to-end proof.
**Why deferred:** Needs a human decision on WHICH dialogue-response field to assert on for "NPC recalls the
consolidated memory" (see review §4 / L6 evidence).
**To fix:** Pick the assertion field; write a two-session e2e scenario; wire into the e2e battery.

---

## ISSUE-108: `scheming_engine.advance_step` creates a SCHEME_STEP edge with no paired Event
**Found:** 2026-06-14, during /fix-parallel SEV-01 (W1 adjacent finding)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/engines/scheming/scheming_engine.py` (`advance_step` call to `add_scheme_step(session=...)`)
**Description:** SEV-01 made the AUTO-advance path (`scheme_advance_tick`) mint the Event and link the
SCHEME_STEP atomically in one transaction. The manual `advance_step` path still calls
`add_scheme_step(session=...)` standalone, creating a SCHEME_STEP edge with no paired Event node — a
possible orphan-edge / inconsistent-scheme concern on that separate call site.
**Why deferred:** Different call site and semantics from SEV-01's auto-advance fix (out of that task's scope).
**To fix:** Decide whether the manual step path must also mint/refer to an Event; if so, route it through an
atomic `run_in_tx` like the auto-advance path (pass `tx=`).

---


## ISSUE-114: `quest_reward_repository.py` has 3 functions > 40 lines (R006 violations)
**Found:** 2026-06-17, during SEV-24 Wave 5 check-rules run
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/repositories/quest_reward_repository.py` — `apply_rewards_atomic`, `_apply_in_tx`, `_collect_delivery_in_tx`
**Description:** Three transaction-helper methods exceed the 40-line hard limit (R006). They were introduced
in the quest cluster wave without triggering the baseline, and Wave 5 now exposes them. Splitting is
artificial: all three are tightly coupled phases of one Neo4j atomic transaction.
**Why deferred:** Refactoring graph-layer transaction helpers is out of scope for Wave 5 (session cleanup).
**To fix:** Extract `_grant_item_rewards_in_tx` and `_grant_currency_reward_in_tx` helpers from `_apply_in_tx`;
split `_collect_delivery_in_tx` at the possession-check vs transfer boundary.

---

## ISSUE-112: EventHandler high-severity witness recording is dead code
**Found:** 2026-06-16, during /fix-next SEV-24 (events slice)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/events/event_handler.py::_record_witnesses`
**Description:** The post-emit witness block reads `actor_id = raw_props.get("src_character_id", "") or None`,
but `_build_event` never sets `src_character_id`, so `actor_id` is always `None` and the WITNESSED edges are
never recorded. Only the `get_characters_at_location` read still fires (a wasted DB round-trip on every
severity ≥ HIGH_SEVERITY_THRESHOLD event). Behaviour was preserved verbatim through the SEV-24 migration.
**Why deferred:** Wiring an actor source into event templates is a feature change outside the repository-facade
slice; preserving exact behaviour was the migration's contract.
**To fix:** Either add `src_character_id` to `EventTemplate`/`_build_event` so witnessing actually fires, or
drop the dead block (and its read) if event-actor witnessing is not a desired feature.

