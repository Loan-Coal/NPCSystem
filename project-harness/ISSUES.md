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

## Open

---

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
**Update (2026-06-22, engine-quality remediation):** Reviewed for a deterministic fix; **none exists** —
the residual is voice-judge strictness + LLM variance, and both candidate levers need an Ollama A/B to
verify (not deterministic). Note the demo seed's own descriptor reinforces the disliked habit:
`captain_sorn`'s `voice_descriptor` in `demo_game/seed.py:688` ends "Every sentence lands like a report to
a superior officer" — the "report" framing nudges toward third-person "reports/scouts" relay. Two minimal
levers remain, each LLM-variance-prone: (a) relax the tone judge in `evals/cases/case_voice_captain_sorn.yaml`
to accept a commander relaying field intel ("reports of skirmishes", "my scouts confirm") as authoritative;
(b) reword the seed `voice_descriptor` toward first-person command. **Kept OPEN (no churn)** per the
"recommend OPEN rather than churn prompts when no confident deterministic fix exists" guidance. Anti-
hallucination guards remain unaffected (separate axis).

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


---


---




---
