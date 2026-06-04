# NPC Engine — Demo Walkthrough (live-verified)

**Captured:** 2026-06-04, final hardening review, against a **fresh-seeded world** on the current
build (`make demo-run`, live Ollama `qwen2.5:14b`). This documents *observed* behavior, not intended
behavior — transcript excerpts are real engine output. Raw log:
`project-harness/review-evidence/final/demo-run-final.log`.

## How to reproduce

```bash
docker-compose down -v && BUILD_SHA=$(git rev-parse --short HEAD) docker-compose up -d --build
# wait for /health 200, then:
make demo-seed          # fresh world: 5 NPCs, 3 locations, 3 factions, player + amulet
make demo-run           # scripted scenario (live LLM)
```
> Run on a **fresh world**. An NPC that accumulates a lot of knowledge across many runs can exceed
> the prompt token budget and degrade dialogue to canned responses (ISSUE-059); a fresh seed avoids
> this until that fix lands.

## Verified-live core (the headline capabilities)

**1. Boot + health.** Container builds from the current tree and serves `/health`
(`{"status":"ok","version":"<sha>"}`) — the build SHA proves you're not on a stale image (L9-05).

**2. Single full-tier dialogue** (direct call, fresh world, ~7s):
> Player → mira_innkeeper: *"Good evening, what news of the town?"*
> **Mira:** *"Evening to you. The usual quiet, but there's a soldier who passed through earlier
> today. Said something about northern armies moving closer to our border. Can't say if it's true
> or not, but he looked pretty shaken up."* — `degradation_level: "full"`, in-character, hedged.

**3. ACT 1 — world event + gossip distortion across NPCs (the core demo).** Firing the `war` epoch
(world-state update now works via the partial-update fix, L9-02) and advancing the clock, the same
"northern war" fact surfaces in each NPC's voice at a different fidelity — direct knowledge vs hedged
rumor vs embellished distortion:

| NPC | Knowledge | Live response (excerpt) |
|-----|-----------|--------------------------|
| Captain Sorn | direct (`KNOWS_ABOUT northern_war_begins`) | *"The northern armies have crossed the border. We are at war."* |
| Mira (innkeeper) | second-hand, hedged | *"I've heard whispers of movement along the border, but nothing I can confirm. A soldier… mentioned the Iron Guard advancing. Hard to know what's true these days."* |
| Old Henryk | distorted / embellished | *"The northmen have overrun king's pass, and the reports speak of thousands dead… just like in my days when I ran dispatches through that road during the last war."* |

This is the anti-hallucination + gossip-distortion thesis demonstrated live: NPCs speak only from
their own (possibly distorted) knowledge, in distinct voices.

**4. ACT 2 — engine-generated quest + emotional reaction.** The quest
`aldric_deliver_quest` ("Aldric wants the ancient amulet returned") is read as `offered`; Aldric
responds in character to the fire + war (*"The fire was a risk to my investments… the northern war
is more troubling; it could disrupt trade routes and inflate prices."*) and his emotion reads
`neutral (valence=-28, arousal=38)`.

## Scripted-runner status (act-by-act, honest)

| Act | Status | Note |
|-----|--------|------|
| ACT 1 — war epoch + propagation | ✅ live | world-state partial update fixed (L9-02) |
| ACT 2 — quest + Aldric dialogue/emotion | ✅ live (one non-fatal traceback mid-act) | |
| ACT 3 — bribe Lira (player↔faction standing) | ❌ blocked | **ISSUE-060**: bribe uses `STANDS_WITH` (a faction→faction edge) for a player→faction standing → 404 |
| ACT 4–7 | ⏸ unreached | blocked behind ACT 3 |

`make demo-run` currently exits non-zero at ACT 3. This is a **pre-existing** demo bug (it was
masked by the earlier ACT-1 world-state 422, which this review fixed). The core engine narrative
(ACTs 1–2) runs live with real LLM output.

## To make the scripted demo run end-to-end
1. Fix **ISSUE-060** (player→faction standing must use a Character→Faction edge, not `STANDS_WITH`).
2. Re-run `make demo-run` on a fresh world and fix any further act-level breakage (untested past ACT 3).
3. For a knowledge-heavy long session, land **ISSUE-059** (bound tier-A context) so dialogue never
   silently degrades to canned.

## What this proves about the engine
The differentiators are real and observable: persistent per-NPC knowledge, gossip propagation with
voice-appropriate distortion, engine-generated quests, and emotion state — all driven by a live local
LLM through the HTTP API, with the demo client as a pure standalone consumer (no `src/` imports).
The remaining gaps are demo-scripting/seed-contract bugs (ISSUE-060) and a context-budget scalability
fix (ISSUE-059), not core-engine failures.
