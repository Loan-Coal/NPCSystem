# DEMO_EXPANSION_ROADMAP.md — D5 synthesis

**Run:** Demo-Game Full Expansion Review (orchestration: `DEMO_GAME_EXPANSION_REVIEW.md`).
**Inputs:** `DEMO_INTENT.md` (D0), `DORMANT_ENGINES.md` (D1), `CONTENT_PLAN.md` (D2), `ECONOMY_DEPTH.md` (D3), `FEASIBILITY.md` (D4).
**Scope:** pygame-ce demo only · zero `src/` imports · read-only analysis (no source changed).

---

## 0. The headline answer

> **The smallest set of phases that flips this from "tech demo" to "a game":**
> **Phase 1 alone** — a multi-objective win/lose economy (gold + faction + deadline + a real reachable failure + an end grade) wired over the **branch primitive** (`DEMO-D2-06`) so player choices fork outcomes, plus the **oath swear/list** verb and **tension HUD** that already ship with zero engine work. That is **15 type-A specs, no engine code**, and it is sufficient to make the demo *play* like a game. Phases 2–3 then deepen the *moat story* (treaty diplomacy, investigation deduction, chapter pacing) via four small engine enablers (E-1..E-4) — they make it a *better* game and a *sharper sales artifact*, but they are not required to clear the "is this a game?" bar.

The core problem D0 named — *every rich verb collapses into one scalar faction gate, and the only failure state is scripted and unreachable* — is **fully fixable demo-side**. The economy redesign (D3) + the branch primitive (D2-06) are the whole fix. The engine enablers are upside, not unblock.

---

## 1. Scored & sequenced master table

Scoring: **PV** player-value · **DF** demo/sales-fit · **Eff** effort (S/L = easy/hard) · **R** reachability (A ship-now / B engine-enabler / C needs-decision) · **Dep** prerequisites. Sorted into phases by `high PV × low friction × unblocks-others`, front-loading type-A.

| ID | Title | Pillar | PV | DF | Eff | R | Dep | Phase |
|----|-------|--------|----|----|-----|---|-----|-------|
| **D2-06** | Branch primitive ⭐ | content | high | high | L | A | — | **1** |
| **D3-02** | Gold as win/lose axis | economy | high | high | S | A | — | **1** |
| **D3-01** | Multi-objective win (faction/wealth/quest) | economy | high | high | M | A* | D3-02 | **1** |
| **D3-04** | Tick deadline pressure | economy | high | med | M | A | auto-tick on | **1** |
| **D3-05** | ≥2 distinct failure states | economy | high | high | S | A | D3-02, D3-04 | **1** |
| **D3-06** | End-screen score/grade | economy | high | high | M | A | D3-01/02/04 | **1** |
| **D1-05** | Tension-meter HUD | dormant | med | high | S | A | — | **1** |
| **D1-01a** | Oath swear/list verb | dormant | high | high | S | A | — | **1** |
| **D1-06a** | Authored `CONTROLS` lose-trigger | dormant | high | med | S | A | D2-06 | **1** |
| **D2-03** | Factions 3→5 | content | med | med | S | A | — | **2** |
| **D2-02** | Locations 3→7 + districts | content | med | med | S | A | — | **2** |
| **D2-01** | Cast 5→11 | content | high | high | M | A | seed split | **2** |
| **D2-04** | Quests ~6→18 (6 chains) | content | high | high | L | A | D2-01 | **2** |
| **D2-05** | Rival quest variants | content | med | med | M | A | accept-guard | **2** |
| **D2-07** | BranchBeat in scripted scenes | content | med | high | M | A | D2-06 | **2** |
| **D2-08** | Promote Village/Tavern to playable | content | high | med | L | A | game_end_checker de-hardcode | **2** |
| **D3-03** | Faction tension / overreach (A-alt bite) | economy | high | high | M | A | D2-06 | **2** |
| **D1-01b** | Oath **break** verb (consequence) | dormant | high | high | S | **B** | E-1 | **3** |
| **D2-11** | Oath betrayal arc | content | high | high | M | **B** | E-1, D2-06, D2-03 | **3** |
| **D1-02** | Treaty broker/break | dormant | high | high | M | **B** | E-2 | **3** |
| **D2-09** | Treaty-broker quest chain | content | high | high | L | **B** | E-2, D2-06 | **3** |
| **D3-01t** | Treaty win sub-path | economy | med | high | S | **B** | E-2 | **3** |
| **D1-03** | Investigation "solve-the-crime" panel | dormant | high | **high** | M-L | **B** | E-3, crime seed | **3** |
| **D1-04** | Chapter act/season banner | dormant | med | med | S-M | **B** | E-4 | **4** |
| **D2-10** | Chapter-paced campaign (A-fallback now) | content | med | med | M | A→B | E-4 to upgrade | **4** |
| **D1-06b** | Engine military battle sim | dormant | med | med | XL | **C** | DECISIONS | **deferred** |
| **D3-03s** | Server-side auto cross-faction decrement | economy | med | med | M | **C** | DECISIONS | **deferred** |

\* D3-01's faction/wealth/quest paths are A; only the treaty sub-path (D3-01t) is B.

---

## 2. Top 5 do-next

1. **D2-06 — Branch primitive** (A, L). The content keystone. `arc_choice.py` is a dead enum today; a real `branch_node.py` + `branch_state.py` + typed `branch_effects.py` over existing client methods is the seam every consequence mechanic (overreach bite, authored lose-trigger, betrayal arc, scenario forks) plugs into. Build this first or everything downstream stays cosmetic.
2. **D3-02 + D3-05 — Gold axis + ≥2 real failures** (A, S+S). The cheapest, highest-leverage fix to D0's verdict: bankruptcy and deadline are two *player-caused, reachable* failure states that exist nowhere today. Flips "one inert lose" → "you can actually lose, in distinct ways."
3. **D3-01 + D3-06 — Multi-objective win + end grade** (A, M+M). Three win paths (faction OR wealth OR quest-chain) plus an S/A/B/C grade gives agency and replay incentive — the exact things D0 says are missing. All from already-polled state.
4. **D1-01a — Oath swear/list verb** (A, S). The single cheapest *new dormant-engine mechanic* — `post_pledge`/`get_pledges_for_npc` already exist (`client.py:1226/1257`); just a panel + poller. Surfaces the "relationships as durable state" moat with one afternoon of demo work.
5. **E-2 + D1-02 — Treaty diplomacy** (B, M). The top keystone *enabler*: three ~12-line client wrappers of the existing `treaties.py` route unlock a second tensioned objective, a flagship quest chain (D2-09), and the treaty win path (D3-01t) — 3 specs across all pillars for the lowest engine cost in the plan.

---

## 3. Dependency graph

```
PHASE 1 (all type-A, no engine work)
  D2-06 branch primitive ──┬─> D1-06a authored CONTROLS lose-trigger
                           ├─> (Phase 2) D3-03 overreach bite
                           ├─> (Phase 2) D2-07 BranchBeat
                           └─> (Phase 3) D2-09 / D2-11 arcs
  D3-02 gold axis ─────────> D3-01 multi-win ──> D3-06 grade
  D3-04 deadline ──────────┘            │
  D3-02 + D3-04 ───────────> D3-05 distinct failures
  D1-05 tension HUD        (standalone)
  D1-01a oath swear/list   (standalone)

PHASE 2 (type-A content + tension, depends on Phase 1 seams)
  D2-03 factions ─> D2-01 cast ─> D2-04 quests ─> D2-05 rival variants
  D2-02 locations+districts (standalone)
  D2-08 promote worlds  <── needs game_end_checker de-hardcode (demo-side, from D3 Phase 1)
  D3-03 overreach  <── D2-06

PHASE 3 (engine enablers unlock the moat mechanics)
  E-1 break_pledge ──> D1-01b oath break ──> D2-11 betrayal arc
  E-2 treaty client ──> D1-02 treaty ──> D2-09 treaty quest ; D3-01t treaty win
  E-3 investigations route ──> D1-03 solve-the-crime panel

PHASE 4 (pacing polish)
  E-4 chapters route ──> D1-04 banner ; upgrades D2-10 from A-fallback

DEFERRED (type-C, needs human DECISIONS)
  D1-06b military battle sim  ;  D3-03s server-side auto-decrement
```

**Keystone enablers (from D4):** **E-2** treaty client methods (unblocks 3) · **E-1** `break_pledge` wrapper (unblocks 2, cheapest) · **E-3** investigations read route (unblocks 1, highest demo-fit). All three are small/low-risk; two are pure client wrappers of routes that already exist, one is a read-only GET route over an already-written engine function.

---

## 4. Phase summary

| Phase | Theme | Specs | Engine work | Outcome |
|-------|-------|-------|-------------|---------|
| **1** | "It's a game now" — economy + branching + first verbs | D2-06, D3-01/02/04/05/06, D1-05, D1-01a, D1-06a | **none** | Multi-objective win, ≥2 reachable failures, end grade, choices fork outcomes, oath verb, tension HUD. **Clears the demo→game bar with zero engine code.** |
| **2** | "There's enough to play" — content volume + tension | D2-01/02/03/04/05/07/08, D3-03 | none (1 demo-side de-hardcode) | 11 NPCs, 7 locations, 5 factions, 18 quests in chains, faction overreach bites, scripted scenes branch, Village/Tavern playable. |
| **3** | "It shows the moat" — diplomacy, oaths, deduction | E-1→D1-01b/D2-11, E-2→D1-02/D2-09/D3-01t, E-3→D1-03 | 3 small enablers | Break an oath and feel the relationship turn; broker/break treaties as a win axis; solve a crime from graph contradictions. The sales-artifact mechanics. |
| **4** | "It has shape" — pacing polish | E-4→D1-04, D2-10 upgrade | 1 read-only route | Chapter/act banners, engine-driven campaign pacing. |
| **deferred** | Needs a human call | D1-06b, D3-03s | DECISIONS | Full military sim; emergent server-side faction decrement. |

---

## 5. Notes carried forward

- **Two D4 corrections changed the plan:** the reachable LOSE state and the faction-overreach "bite" are **both type-A** (writable today via `upsert_edge`/`adjust_npc_reputation`) — they moved out of "blocked/needs-decision" into Phase 1/2. Only the *engine simulation* versions are deferred type-C.
- **Structural constraint for the D3 implementation task:** `evaluate_game_end` must be split into `check_win_multi` / `compute_grade` / failure-selection helpers to stay within the 40-line / 3-nesting rules (FEASIBILITY §5).
- **D2-01 forces a seed split** (`demo_game/seed_npc_data.py`) to respect the file-size rule under the existing waiver — needs a one-line DECISIONS entry when implemented.
- **Open human calls** (see `OPEN_QUESTIONS.md`): sandbox vs authored-campaign framing, session length / deadline tuning, auto-tick default, and the two deferred type-C decisions.
