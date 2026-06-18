# RECONCILIATION.md — demo-expansion analysis vs the shipped EXP-201..230 program

**Written:** 2026-06-12. **Why:** the demo-expansion analysis (`DEMO_INTENT.md`, `DORMANT_ENGINES.md`,
`CONTENT_PLAN.md`, `ECONOMY_DEPTH.md`, `FEASIBILITY.md`, `DEMO_EXPANSION_ROADMAP.md`, `OPEN_QUESTIONS.md`)
was produced against the codebase **before** the EXP-201..230 expansion landed and before ROADMAP Phase F/G
existed. This note records the deltas so the analysis is not read as current truth, **without** re-running the
multi-agent review. The actionable, reconciled form is **ROADMAP Phase H** (driven by `DEMO_BUILD_LOOP.md`).

## Mental model (owner, 2026-06-12)
> Phases **F/G surface the internal engines as API**; the **demo-expansion (Phase H) consumes that API** to make
> the demo a game. They are sequential layers, not competitors. Phase H is the demo-side consumer track.

## What changed under the analysis (verified in code)

| Analysis claim | Status now | Evidence |
|---|---|---|
| Baseline "5 NPCs / 3 locations / 3 factions" (`DEMO_INTENT.md`, `CONTENT_PLAN.md`) | **STALE → 8 NPCs / 4 locations / 3 alliable factions (+iron_legion)** | EXP-223 added Sera/Harwick/Nel + the Chapel: `seed.py:488-520` (`_NPCS`), `seed.py:468-474` (`_LOCATIONS`). Rebaseline D2 targets from 8/4, not 5/3. |
| "Branch is build-from-scratch; `arc_choice.py` is a dead enum" (`CONTENT_PLAN.md` D2-06) | **SOFTENED** — an engine-level quest-branch primitive now exists | EXP-218 shipped `choose` + `POST /quest/{id}/choose` (ROADMAP EXP-218; DEC-101). The demo just lacks a **client wrapper** (`post_quest_choice` is absent from `client.py`). So D2-06 leans on that route via a small wrapper (now **H0.5**), not pure from-scratch. |
| "Investigation is a dormant legacy engine to surface" (`DORMANT_ENGINES.md` D1-03) | **PARTIAL OVERLAP** — investigation is revived by EXP-229 detection | ROADMAP F1.6 wires `investigation` into the scheduler to discover schemes; F2.3 adds a `schemes.py` read route. The "solve-the-crime" panel (H3.3) should **reuse the schemes/discovery surface where it fits** and only add a dedicated `investigations.py` route (E-3) for the alibi/contradiction half that schemes don't cover. |
| `game_end_checker.py` single-win / inert-lose (`ECONOMY_DEPTH.md`) | **UNCHANGED — D3 analysis fully valid** | `game_end_checker.py:17-28,106-117` still: win = 2 of 3 factions ≥ 50; lose = `iron_legion` controls `loc_guard_barracks` (inert). The entire economy-depth pillar (H1) applies as written. EXP-223 only reviewed faction-count, did not deepen win/lose. |
| Reachability A/B/C in `FEASIBILITY.md` | **STILL VALID**; F2 adds *cognition* routes (player_model/schemes/phase), not the legacy ones | Confirmed only `pledges.py` + `treaties.py` exist among the legacy targets; `investigations.py`/`chapters.py` still absent. E-1..E-4 enablers remain net-new and distinct from Phase F2's routes → they become **H0**. |

## Net effect on the plan
- **Pillar 3 (economy, H1):** unchanged and still the highest-leverage demo→game fix. Ships type-A.
- **Pillar 2 (content, H2):** rebaseline counts to 8 NPC / 4 loc; branch primitive (H2.1) wraps EXP-218's
  `choose` route (H0.5) instead of inventing one.
- **Pillar 1 (legacy engines, H3):** treaty/oath/chapter unchanged (need H0 enablers E-1/E-2/E-4);
  investigation (H3.3) reconciled to reuse EXP-229's schemes/discovery surface + a thin E-3 route.
- **No conflict with F/G:** F/G surface the *cognition* engines (player-model, schemes, director, proactive,
  deception); H surfaces *economy + content + legacy gameplay* engines. Phase H consumes F's routes and adds
  only the four small legacy enablers (H0).

See **ROADMAP.md Phase H** for the sequenced, rebaselined checklist and **DEMO_BUILD_LOOP.md** for the overnight runbook.
