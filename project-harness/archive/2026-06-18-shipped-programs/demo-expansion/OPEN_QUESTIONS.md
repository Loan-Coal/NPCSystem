# OPEN_QUESTIONS.md — decisions only the human can make

Each item lists the **educated-guess default** the review used so nothing is blocked. If a default is wrong, the linked specs change; otherwise the roadmap proceeds as written. Cross-refs: `DEMO_EXPANSION_ROADMAP.md`, `FEASIBILITY.md`.

---

## OQ-1 — Is the demo a sandbox or a 30-minute authored campaign?
**Why it matters:** Drives D2 content shape (replayable scenario picker vs one linear arc) and D3 win/lose framing (open objectives vs scripted climax).
**Default used:** **Replayable sandbox with authored scenarios** — a Free-Play world plus 2–3 pickable scenarios (Tavern/Village promoted to playable, D2-08), each with multi-objective win and a graded end-card. This maximizes "a person would actually play it again" while still giving a studio a tight 5-minute scripted reel (`make demo-run`).
**Affects:** D2-06, D2-07, D2-08, D2-10, D3-06.

## OQ-2 — Target session length / deadline tuning?
**Why it matters:** D3-04 (tick deadline) and D3-06 (grade thresholds) need concrete numbers; too tight = frustrating, too loose = no pressure.
**Default used:** **~50–80 ticks per scenario** as the deadline window, gold win at 500, faction win at standing ≥ 50 with ≥2 factions (unchanged), quest-chain win at 3 of N. These are placeholders for balance — flagged as tuning constants, not architecture.
**Affects:** D3-01, D3-04, D3-06.

## OQ-3 — Should auto-tick be ON by default in the playable demo?
**Why it matters:** D3-04's deadline pressure only bites if the clock advances on its own. Today the demo may advance ticks only on explicit action.
**Default used:** **Auto-tick ON for playable Free-Play / scenarios, OFF for the scripted reel** (the reel controls its own pacing). This is a loop/config default, not engine work.
**Affects:** D3-04, D3-05.

## OQ-4 — How far do we surface the moat as *explainability* vs *gameplay*?
**Why it matters:** D1-03 (investigation) and D1-05 (tension HUD) can be framed as "look how auditable the graph is" (sales) or as a real deduction puzzle / pressure gauge (game). The two pull UI in slightly different directions.
**Default used:** **Gameplay-first, with an inspect affordance** — the investigation panel is a playable solve-the-crime mechanic, but every clue links back to its graph provenance (rumor trace / belief source) so the sales story ("auditable, no hallucinated state") is one click away.
**Affects:** D1-03, D1-05, plus the existing `inspect_panel.py`.

## OQ-5 — [type-C] Does an `Army`/military unit get a player-adjustable `strength`, and what verb drives it?
**Why it matters:** This is the only way to make the LOSE state *emergent* (a real losable battle) rather than *authored* (a scripted trigger). It is a schema + design decision, not a pure enabler.
**Default used:** **Defer.** Phase 1 ships an **authored** `CONTROLS` lose-trigger (D1-06a, type-A) so a reachable failure exists now. The full military simulation (D1-06b) waits for a DECISIONS entry answering: army strength field? player verb (reinforce / sabotage / bribe-captain / quest-reinforce)? balance model?
**Affects:** D1-06b (deferred).

## OQ-6 — [type-C] Should friendly actions auto-decrement a rival faction server-side?
**Why it matters:** D3-03 "faction tension" can either be *authored* (the demo applies a rival penalty as a quest/branch effect via `adjust_npc_reputation`, type-A) or *emergent* (the engine auto-lowers rivals on every friendly action, which touches faction/reputation engine behavior and possibly an `OPPOSES` edge schema).
**Default used:** **Author it demo-side now** (D3-03 type-A bite via branch/quest effects), **defer** the emergent server-side decrement (D3-03s) to a DECISIONS call.
**Affects:** D3-03 (now), D3-03s (deferred).

## OQ-7 — Content authoring budget: how much new dialogue/quest prose?
**Why it matters:** D2-04 (18 quests) and D2-01 (11 NPCs) imply real authored content; LLM-generated dialogue keeps cost low but reduces authorial control of the demo narrative.
**Default used:** **Hybrid** — structural content (NPCs, quests, factions, branch nodes) is hand-authored in `seed.py`; in-scene NPC dialogue stays LLM-generated through the existing dialogue engine (showcasing the moat). Only the scripted reel uses cached/pinned lines.
**Affects:** D2-01, D2-04, D2-09, D2-11.

## OQ-8 — Do we keep the single Free-Play world canonical, or make all three worlds first-class?
**Why it matters:** D2-08 promotes Village/Tavern to playable, which requires de-hardcoding `game_end_checker` constants per world (demo-side refactor, no engine work).
**Default used:** **Make all three first-class** — parameterize `game_end_checker` win/lose constants per world so each scenario has its own objectives. This is the replayability payoff and is pure demo-side work.
**Affects:** D2-08, D3-01.
