# FEASIBILITY.md — D4: reachability gate, enabler catalog, ship-now split

**Lens:** D4 (Feasibility & enablers). Read-only verification of every D1/D2/D3 proposal against the actual code in `src/npc_engine/api/routes/`, `demo_game/client.py`, and the engine packages. Applies the §3 reachability gate (`DEMO_INTENT.md`): **A** = pure demo-side (client method exists or state already polled + UI/loop work only); **B** = needs an engine-side enabler (new `api/routes/*.py` and/or an `EngineClient` method); **C** = needs a schema/layer/DECISIONS human call.

All A/B/C labels below are **verified against code**, not taken on the lens's word. Where a lens mislabelled, the row is marked **[CORRECTED]** with the evidence.

> Cross-refs: `DEMO_INTENT.md` (D0 rubric/baseline), `DORMANT_ENGINES.md` (D1), `CONTENT_PLAN.md` (D2), `ECONOMY_DEPTH.md` (D3), `DEMO_EXPANSION_ROADMAP.md` (D5 synthesis), `OPEN_QUESTIONS.md`.

---

## 0. Verification log (what I confirmed in code)

| Claim under test | Result | Evidence |
|---|---|---|
| `pledges.py` route exists with create/list/break | **TRUE** | `pledges.py:66` (`POST /characters/{id}`), `:95` (`GET`), `:114` (`POST .../break`) |
| `EngineClient.post_pledge` + `get_pledges_for_npc` exist | **TRUE** | `client.py:1226`, `client.py:1257` |
| `EngineClient.break_pledge` exists | **FALSE — missing** | grep for `break_pledge`/`def break` in `client.py` → 0 matches |
| `treaties.py` route exists (create/list/expire/break) | **TRUE** | `treaties.py:71` (`POST /`), `:96` (`GET /factions/{id}`), `:113` (`/expire`), `:132` (`/break`) |
| Any `EngineClient` treaty method exists | **FALSE — zero** | grep `treaty|treaties` in `client.py` → 0 matches |
| `api/routes/investigations.py` exists | **FALSE** | not in routes glob; `get_investigation_context` is `async`, query-only at `investigation/investigation_engine.py:39` |
| `api/routes/chapter(s).py` / `story_pacing.py` exist | **FALSE** | not in routes glob; `get_current_chapter` is an engine fn (`chapter/chapter_engine.py:32,124`) |
| story_pacing fields reach the demo via `get_world_state` | **TRUE (D1-05 confirmed A)** | `world_state_writer.py:32-33` persists `max_event_severity`/`quest_generation_rate` to the Neo4j node; `get_world_state` returns `properties(w)` (`client.py:178-197`); writer query `RETURN properties(w)` (`world_state_writer.py:35`) |
| `PART_OF` reachable from demo (`post_part_of`) | **TRUE** | `client.py:776`; used in `seed.py` |
| Gold polled (`currency_balance`) | **TRUE** | `gold_poller.py:48-62` |
| Clock readable (`get_clock_state().current_tick`) | **TRUE** | `client.py:310` |
| `get_quest(quest_id).status` readable | **TRUE** | `client.py:891` |
| `adjust_npc_reputation` exists | **TRUE** | `client.py:1386` |
| `CONTROLS` edge writable from the demo without a new route | **TRUE — affects D1-06/D3-03 [NEW FINDING]** | `factions.py:196` `set_controls` + `:210` `remove_controls`; generic `EngineClient.upsert_edge(edge_type, src, dst)` (`client.py:478`) can write any registered edge type via `POST /v1/graph/edges/{edge_type}`. The demo already uses `upsert_edge("STANDS_WITH")` in seed. |

**Headline correction from the verification:** the demo can already *write a `CONTROLS` edge* (via `upsert_edge` or a `set_controls` client wrapper of `factions.py:196`). This changes the lens framing of the LOSE state: making `iron_legion` "take the barracks" is **not** gated on a new military route — it is gated on a *design decision* about what player action should trigger that write. The military *battle simulation* is still type-C, but a demo-authored lose trigger (a branch effect / quest-fail effect that writes `CONTROLS`) is type-A. See §5 note on D1-06.

---

## 1. Master classification table

Effort is **demo-side build cost** (S/M/L/XL). "Prereq enablers" lists the engine-side work this spec is blocked on (empty = ships now).

| ID | Pillar | Lens-claimed | **D4 verified** | Effort | Prerequisite enablers |
|----|--------|--------------|-----------------|--------|------------------------|
| **DEMO-D1-01** Oath swear/list | dormant | A (swear) / A-adj (break) | **A (swear+list); B (break)** **[CORRECTED]** | S | `EngineClient.break_pledge` (E-1) for the break verb only |
| **DEMO-D1-02** Treaty broker/break | dormant | B | **B** ✓ | M | `EngineClient.create_treaty/get_faction_treaties/break_treaty` (E-2) |
| **DEMO-D1-03** Investigation panel | dormant | B | **B** ✓ | M-L | `api/routes/investigations.py` + `EngineClient.get_investigation` (E-3); + seeded crime content (D2) |
| **DEMO-D1-04** Chapter banner | dormant | B | **B** ✓ | S-M | `GET /chapters/current` route + `EngineClient.get_current_chapter` (E-4) |
| **DEMO-D1-05** Tension-meter HUD | dormant | A (read-only) | **A** ✓ **(verified: fields persisted + serialized)** | S | none |
| **DEMO-D1-06** Player-influenced battle → reachable LOSE | dormant | C | **C for battle sim; A for a demo-authored `CONTROLS` lose-trigger** **[CORRECTED]** | L-XL (sim) / S (authored trigger) | DECISIONS call on the military verb (engine sim); OR none for a demo-side authored trigger via `upsert_edge` |
| **DEMO-D2-01** Cast 5→11 | content | A | **A** ✓ | M | none (D2-02 ordering only) |
| **DEMO-D2-02** Locations 3→7 + districts | content | A | **A** ✓ (`post_part_of` confirmed) | S | none |
| **DEMO-D2-03** Factions 3→5 | content | A | **A** ✓ | S | none |
| **DEMO-D2-04** Quests ~6→18 | content | A | **A** ✓ (full lifecycle on client) | L | none (D2-01 ordering) |
| **DEMO-D2-05** Rival quest variants | content | A | **A** ✓ — but needs a `GameController` accept-guard (loop change, type-A) | M | none; flag accept-guard as an ISSUE |
| **DEMO-D2-06** Branch primitive ⭐ | content | A (high-effort) | **A** ✓ — pure demo orchestration over existing methods | L | none (it is itself the content keystone) |
| **DEMO-D2-07** BranchBeat in scenes | content | A (dep D2-06) | **A** ✓ | M | DEMO-D2-06 (demo-side dep, not an engine enabler) |
| **DEMO-D2-08** Promote Village/Tavern | content | A | **A (content) — but blocked on a demo-side de-hardcode of `game_end_checker`** **[NOTED]** | L | none engine-side; depends on D3 parameterizing `game_end_checker` constants (demo-side) |
| **DEMO-D2-09** Treaty-broker quest | content | B | **B** ✓ | L | E-2 (treaty client methods); + DEMO-D2-06 |
| **DEMO-D2-10** Chapter campaign banner | content | B (with A fallback) | **B; A-fallback confirmed viable** ✓ | M | E-4 for engine-driven; A-fallback (quest-count-driven banner) needs none |
| **DEMO-D2-11** Oath betrayal arc | content | B (break) / A (swear) | **A (swear); B (break)** ✓ same as D1-01 | M | E-1 (`break_pledge`); + DEMO-D2-06, DEMO-D2-03 |
| **DEMO-D3-01** Multi-objective win | economy | B (treaty sub-path) / A (rest) | **A (faction/wealth/quest); B (treaty)** ✓ | M | E-2 for treaty sub-path only |
| **DEMO-D3-02** Currency win/lose axis | economy | A | **A** ✓ (`GoldPoller` runs) | S | none |
| **DEMO-D3-03** Faction tension/overreach | economy | A (detect) / B (bite) | **A (detect+gate); B (server-side decrement) — but A-alt exists via demo-side `adjust_npc_reputation`** **[CORRECTED]** | M | none for detect; for "bite", **no new route needed** — demo can call `adjust_npc_reputation` (`client.py:1386`) on the rival as a quest/branch effect (type-A). True server-side auto-decrement on bribe is B/C. |
| **DEMO-D3-04** Time/tick deadline | economy | A | **A** ✓ (`get_clock_state` confirmed) | M | none (needs auto-tick ON — config/loop, not engine) |
| **DEMO-D3-05** Distinct failure states | economy | A (2 failures) / B (overreach) | **A** ✓ (composes D3-02/04; overreach via A-alt above) | S | DEMO-D3-02, DEMO-D3-04 (demo-side) |
| **DEMO-D3-06** Score/grade | economy | A | **A** ✓ | M | DEMO-D3-01/02/04 for multi-axis (demo-side) |

**Mislabels corrected (5):**
1. **D1-01** — lens calls the *break* path "A with a trivial client add". By the §3 gate, a new `EngineClient` method that wraps an unwrapped route **is the definition of type-B** (engine-side enabler, tracked separately). The swear/list path is genuinely A; the break path is **B** (small, but B). Splitting matters for the ship-now front-load.
2. **D1-06** — lens calls it flatly type-C. Verified: a *demo-authored* `CONTROLS` lose-trigger is **type-A** (the edge is writable today via `upsert_edge`). Only the *engine battle simulation* with a balanced military verb is C. This unblocks a reachable LOSE state in Phase 1 without engine work.
3. **D3-03** — lens calls the "bite" path B (needs server-side decrement). Verified: the demo can already *apply* a cross-faction penalty itself by calling `adjust_npc_reputation` (`client.py:1386`) as a quest/branch effect — that is **type-A**. Only a server-side *automatic* decrement-on-friendly-action is B/C. So overreach can bite in Phase 1.
4. **D2-08** — lens calls it A. It is content-A engine-side, but it is *blocked on a demo-side refactor* of `game_end_checker` constants (`game_end_checker.py:17-28`) to be world-parameterized. No engine enabler, but it is **not zero-prereq** — noted so D5 doesn't front-load it as a clean A.
5. **D2-10** — confirmed the A-fallback (quest-chain-count-driven banner) is real, so this can ship a degraded version with **zero** engine work, upgrading to B when E-4 lands.

---

## 2. Enabler catalog (each engine-side enabler listed once)

Sorted by **unblock count** (how many DEMO-NN specs each enabler frees). An enabler is engine-side work (a new route file and/or a new `EngineClient` method) tracked **separately** from the demo task that consumes it.

| Enabler ID | Engine-side work | Route file | `EngineClient` method(s) | Unblocks (count) | Specs |
|---|---|---|---|---|---|
| **E-2** | Wrap existing `treaties.py` route | `treaties.py` (exists) | `create_treaty`, `get_faction_treaties`, `break_treaty` | **3** | DEMO-D1-02, DEMO-D2-09, DEMO-D3-01 (treaty sub-path) |
| **E-1** | Wrap existing break endpoint | `pledges.py` (exists, `:114`) | `break_pledge` | **2** | DEMO-D1-01 (break verb), DEMO-D2-11 (betrayal arc) |
| **E-3** | New read-only route + client | **new** `api/routes/investigations.py` | `get_investigation` | **1** | DEMO-D1-03 |
| **E-4** | New read-only route + client | **new** `api/routes/chapters.py` (`GET /chapters/current`) | `get_current_chapter` | **1** | DEMO-D1-04 (and upgrades DEMO-D2-10 from its A-fallback) |
| **E-5** *(optional convenience)* | Thin wrapper of `factions.py:196` | `factions.py` (exists) | `set_controls` | **0 new** (D1-06 authored-trigger works via existing `upsert_edge`) | convenience for DEMO-D1-06 authored lose-trigger |

**Notes on enabler effort (all small):**
- **E-1, E-2** are pure client wrappers of routes that already exist and already return `OkEnvelope[dict]` — each is the `post_pledge` pattern (`client.py:1226`), ~10-15 lines per method. No engine, no schema, no route change. Lowest-risk engine work in the whole plan.
- **E-3, E-4** each need a *new* route file but both are **read-only `GET`** handlers over engine functions that already exist (`get_investigation_context` async, `get_current_chapter` async). No schema change, no write path. Each is one small route module + a `Depends` wiring in `dependencies.py` + a client `GET` method. Bound by the 300-line rule (trivially under).
- **E-5** is not strictly required — listed only because a named `set_controls` wrapper reads better in demo code than a raw `upsert_edge("CONTROLS", ...)`. The capability is already reachable.

---

## 3. The keystone enablers (max demo value per engine route)

Ranked by unblock-count and by how much of D0's §4 verdict ("multiple tensioned objectives + branching + reachable failure") each one lights up.

### Keystone 1 — **E-2: treaty client methods** (`create_treaty` / `get_faction_treaties` / `break_treaty`)
**Unblocks 3 specs** — the most of any enabler — and they span all three pillars: D1-02 (dormant-engine surfacing), D2-09 (a flagship "consequential auditable world" quest chain), and the **treaty win path of D3-01** (a second tensioned objective axis). The route already exists (`treaties.py:71/96/132`); this is *three ~12-line client wrappers*, the single highest-leverage-to-effort engine task in the entire expansion. This is the clearest keystone: smallest engine cost, broadest unblock, directly serves the §4 "second tensioned objective" mandate.

### Keystone 2 — **E-1: `break_pledge` client wrapper**
**Unblocks 2 specs** (D1-01 break verb, D2-11 betrayal arc) and is the cheapest possible engine task: a single ~10-line wrapper of `pledges.py:114`. It converts the oath surface from "swear and watch" (already shippable, A) into "swear, break, and *feel the relationship turn cold*" — which is the relationships-as-state moat (§1a.3) made into a consequence verb. High moat-fit per line of engine code.

### Keystone 3 — **E-3: `api/routes/investigations.py` + `get_investigation`**
**Unblocks 1 spec** but that spec — D1-03 — is D1's single **highest demo-fit** pick: a "solve-the-crime" panel that surfaces alibi/rumor *contradictions* from the graph IS the knowledge-provenance moat (§1a.2) turned into gameplay. The engine function (`get_investigation_context`, `investigation_engine.py:39`) is already written, async, and query-only; the enabler is a thin read-only route. It is a keystone by *value*, not by count — it is the only enabler that turns a moat claim into a playable deduction puzzle.

**Deliberately NOT a keystone:** a **military battle route** (the D1-06/D3 "make the LOSE reachable" lever). The verification shows the LOSE edge is already writable (`upsert_edge`/`set_controls`), so the *reachable failure* is achievable in Phase 1 with **zero** engine work via a demo-authored trigger. The full balanced military *simulation* is a large, type-C design effort with med demo-fit — explicitly out of the keystone set. (E-4 chapter route is also non-keystone: 1 spec, and that spec has a working A-fallback.)

---

## 4. Ship-now vs blocked split

### (A) Ship now — ZERO engine work (front-load these)
These need **no new route and no new `EngineClient` method** — every method exists or the state is already polled. **15 specs/slices:**

- **DEMO-D1-05** — Tension-meter HUD (verified: pacing fields persisted + serialized via existing `get_world_state`).
- **DEMO-D1-01 (swear+list slice)** — oath panel + `pledge_poller` over `get_pledges_for_npc` (the break verb splits off to B).
- **DEMO-D2-01** — cast 5→11 (seed only).
- **DEMO-D2-02** — locations 3→7 + districts (`post_part_of` confirmed live).
- **DEMO-D2-03** — factions 3→5 (seed only).
- **DEMO-D2-04** — quests ~6→18 (full lifecycle on client).
- **DEMO-D2-05** — rival quest variants (needs a demo-side accept-guard; still A).
- **DEMO-D2-06** ⭐ — branch primitive (`branch_node.py`/`branch_state.py`/`ui/branch_panel.py`; pure orchestration over existing methods).
- **DEMO-D2-07** — BranchBeat (demo-side dep on D2-06 only).
- **DEMO-D3-02** — gold win/lose axis (`GoldPoller` already runs).
- **DEMO-D3-03 (detect + A-alt bite)** — overreach gate; bite via `adjust_npc_reputation` as a quest/branch effect.
- **DEMO-D3-04** — tick deadline (`get_clock_state` confirmed; needs auto-tick ON, a loop/config default not an engine change).
- **DEMO-D3-05** — distinct failure states (composes D3-02/04, all demo-side).
- **DEMO-D3-06** — score/grade (pure function over already-plumbed axes).
- **DEMO-D1-06 (authored-trigger slice)** — a demo-authored `CONTROLS` lose-trigger via existing `upsert_edge` (the *engine battle sim* is excluded; the *reachable failure* ships now).

> Count of clean zero-engine A specs/slices: **15** (13 fully-A specs + the swear-only slice of D1-01 and the authored-trigger slice of D1-06). The "≥2 reachable player-caused failures" mandate (§4) is fully satisfiable with **zero engine work** (D3-02 bankruptcy + D3-04 deadline + the D1-06 authored legion trigger).

### (B) Blocked on an engine enabler (small, well-scoped)
- **DEMO-D1-01 (break verb)** → E-1
- **DEMO-D2-11 (break/betrayal half)** → E-1 (swear half is A)
- **DEMO-D1-02 (treaty)** → E-2
- **DEMO-D2-09 (treaty quest)** → E-2 (+ D2-06)
- **DEMO-D3-01 (treaty win sub-path)** → E-2 (faction/wealth/quest sub-paths are A)
- **DEMO-D1-03 (investigation)** → E-3 (+ seed content)
- **DEMO-D1-04 (chapter banner)** → E-4
- **DEMO-D2-10 (engine-driven chapter)** → E-4 (A-fallback ships without it)

### (C) Needs a schema / layer / DECISIONS human call
- **DEMO-D1-06 — engine battle simulation with a balanced player military verb.** Requires a DECISIONS entry: does an `Army` get a player-adjustable `strength`, and what verb (reinforce/sabotage/bribe-captain/quest-reinforce) drives it? This is economy/design + potential schema, not a pure enabler. *(The reachable-LOSE outcome itself does NOT need this — see the §4(A) authored-trigger slice.)*
- **DEMO-D3-03 — server-side automatic cross-faction decrement** (the engine itself lowering a rival on every friendly action). That touches faction/reputation engine behavior and possibly an `OPPOSES`-edge schema seed — DECISIONS call. *(The "bite" can ship without it via the demo-side A-alt above; this C-item is only for true emergent auto-decrement.)*

---

## 5. Constraint compliance check (demo rules)

- **Zero `src/` import rule:** every type-A spec above is demo-side only. E-1..E-4 are engine-side files (in `src/`), consumed by the demo *only* through `EngineClient` HTTP methods — the boundary is preserved.
- **File-size waivers (DEC-029/032/034/049/074/075):** `client.py` (~1524L) and `seed.py` (~1265L) are waived. New client methods (E-1/E-2 wrappers, get_investigation, get_current_chapter) **append** to the already-waived `client.py` — acceptable. **New** demo code is bound by 300/40/3. Forced splits to name:
  - **D2-01** cast expansion pushes `seed.py` further past its waiver — split NPC data into `demo_game/seed_npc_data.py` (data-only module imported back), per D2's own note. Add a DECISIONS line.
  - **D2-06** branch primitive is *already* correctly factored into 3 small files (`branch_node.py`, `branch_state.py`, `ui/branch_panel.py`) — each well under 300. No split needed; the effect types (`SetBeliefEffect`/`RepDeltaEffect`/...) should live in `branch_effects.py` to keep `branch_node.py` under the limit and respect OCP (new effect = new file).
  - **E-3/E-4** route files are new and trivially under 300L (read-only GET handlers).
- **PYGAME ONLY:** all UI specs (oath/treaty/investigation/chapter panels, branch modal, tension meter, grade card) model on existing `ui/*_panel.py` + the 14-tab `right_panel.py` framework — confirmed pygame-ce, no new UI tech.
- **40-line function / 3-level nesting:** the only at-risk new function is `evaluate_game_end` (D3 widens it with 4+ new params and a failure if-chain). D3 must extract `check_win_multi`, `compute_grade`, and the failure-selection into named helpers to stay ≤40 lines / ≤3 nesting — flag to D5 as a structural constraint on the D3 implementation task.

---

## Orchestrator notes

- **Keystone enablers (3):** **E-2** treaty client methods (`create_treaty`/`get_faction_treaties`/`break_treaty` — wraps existing `treaties.py`; unblocks 3 specs across all pillars — the top pick); **E-1** `break_pledge` client wrapper (wraps `pledges.py:114`; unblocks 2; cheapest, highest moat-fit per line); **E-3** `api/routes/investigations.py` + `get_investigation` (new read-only route over the already-written `get_investigation_context`; unblocks D1-03, the single highest demo-fit spec). All three are small and low-risk (two are pure client wrappers; one is a read-only route).
- **Ship-now type-A count:** **15** specs/slices need ZERO engine work. This includes the entire D3 economy redesign except the treaty win sub-path, the full D2 content+branching expansion, the D1-05 tension HUD, and a genuinely reachable LOSE state — so D0's §4 "multiple tensioned objectives + branching + reachable failure" verdict is satisfiable in Phase 1 with no engine work, and the four small enablers (E-1..E-4) only *deepen* it.
- **Two lens mislabels worth flagging to D5:** (1) the LOSE state is reachable today via `upsert_edge`/`factions.py:196 set_controls` — D1/D3 over-classified it as C; (2) D3-03 overreach can *bite* today via demo-side `adjust_npc_reputation` — only true server-side auto-decrement is B/C.
