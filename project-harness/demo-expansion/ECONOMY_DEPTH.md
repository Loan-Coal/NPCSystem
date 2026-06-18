# ECONOMY_DEPTH.md — Pillar 3: win/lose economy depth (lens D3)

**Lens:** D3 (economy depth). Scores against the D0 rubric (`DEMO_INTENT.md` §3) and
fixes the §4 verdict: today every rich verb collapses into one scalar gate, and the lone
lose state is scripted, player-inert, and structurally unreachable.
**Scope:** read-only analysis + this one file. Every delta below is to
`demo_game/game_end_checker.py`'s constants/logic, computed from REST-polled state the demo
**already reads**, or names the poll/route enabler. PYGAME ONLY; demo has zero `src/` imports.

---

## 0. The current win/lose logic — verbatim (so deltas are unambiguous)

From `demo_game/game_end_checker.py`:

```python
# game_end_checker.py:16-28
WIN_STANDING_THRESHOLD: int = 50            # :17
WIN_MIN_FACTIONS: int = 2                   # :18
DEMO_FACTIONS: tuple[str, ...] = ("merchants_guild", "city_guard", "thieves_guild")  # :21
LOSE_LOCATION_ID: str = "loc_guard_barracks"  # :27
LOSE_FACTION_ID: str = "iron_legion"          # :28
```

```python
# game_end_checker.py:86-117
def check_win(faction_standings: dict[str, int]) -> bool:
    qualified = sum(
        1
        for faction in DEMO_FACTIONS
        if faction_standings.get(faction, 0) >= WIN_STANDING_THRESHOLD
    )
    return qualified >= WIN_MIN_FACTIONS          # :103

def check_lose(iron_legion_controls: list[str]) -> bool:
    return LOSE_LOCATION_ID in iron_legion_controls   # :117
```

```python
# game_end_checker.py:146-151 (inside evaluate_game_end)
outcome: Literal["win", "lose"] | None = None
if check_lose(iron_legion_controls):     # lose checked BEFORE win :147
    outcome = "lose"
elif check_win(standings):               # :149
    outcome = "win"
```

**Polling surface today** (`game_end_poller.py:103-117`): `_poll_once` calls
`client.get_npc_reputation(player_id)` → `reputation` records, and
`client.get_graph_edges("CONTROLS", src_id="iron_legion")` → `controlled_locations`,
then `evaluate_game_end(reputation, controlled_locations, arc_faction=...)`. Errors are
swallowed and prior state retained (`:125-126`). The render loop reads `get_state().outcome`
in `game_window.py:422-426` and freezes the game on the first non-`None` outcome.

**The structural problem (D0 §4 confirmed):** `check_lose` only ever fires if
`iron_legion` gains a `CONTROLS` edge to `loc_guard_barracks`, and per the comment at
`game_end_checker.py:24-26` the legion can *only* ever control that one location, written by a
**scripted clock tick** (`military_battle_service`, ACT 5 of `run.py:261-279`) — nothing the
player does feeds it. So the demo has **one win path and one decorative lose path.** Every
delta below adds a player-reachable axis on top of the existing `evaluate_game_end` switch.

**Reachability note (the hard boundary):** `evaluate_game_end` is a *pure* function — it only
sees whatever the poller fetches and passes in. Type-A proposals reuse data the poller already
fetches (reputation) OR data another existing poller already reads (`GoldPoller.get_gold()`
via `get_node("Character", player_id).currency_balance`, `gold_poller.py:61-62`;
`get_clock_state().current_tick`, `client.py:310-321`; `get_quest(quest_id).status`,
`client.py:891-907`). For those, the only engine-side work is **widening
`evaluate_game_end`'s parameters and adding the fetch to `game_end_poller._poll_once`** — both
demo-side files, zero new route. Type-B proposals need a brokered-treaty / aggregate-wealth
route that does not yet exist.

---

## 1. Design spine — one shared end-state model

All six specs below are deltas to **one** widened evaluator. Rather than restate the plumbing
six times, the shared change is: `evaluate_game_end` gains keyword params
(`total_gold: int | None`, `current_tick: int | None`, `completed_quest_ids: frozenset[str]`,
`treaty_signed: bool`, plus per-axis thresholds as module constants), and
`game_end_poller._poll_once` fetches each from the named poller/client method and passes it in.
`ObjectiveState` (`game_end_checker.py:45-60`) gains optional fields
(`total_gold`, `ticks_remaining`, `win_path`, `grade`, `failure_reason`) so the
`game_window` end overlay (`:501-527`) can render *which* path won/lost and the grade.
Each spec is the **minimal independent slice** of that spine and can ship alone.

---

## 2. The six mini-specs

### DEMO-D3-01: Multi-objective victory (faction OR wealth OR quest-chain OR treaty)
Pillar: economy
Player fantasy: "There's more than one way to save this town — coin, steel, shadow, or a signed peace — and I get to pick mine."
Why it matters: directly answers D0 §4 ("exactly one thing to achieve, one way choices matter"). Replayability jumps from 1 path to ≥3; sales-fit is high because each path *showcases a different moat surface* (reputation propagation, currency loop, quest provenance, treaty/relationship-stakes) rather than nudging one number.
Current state: single win gate `check_win` returns `qualified >= WIN_MIN_FACTIONS` (`game_end_checker.py:98-103`); `evaluate_game_end` only `elif check_win(standings)` at `:149`.
Engine capability used: reputation via `get_npc_reputation` (`client.py:199-216`, already polled `game_end_poller.py:104`); gold via `GoldPoller.get_gold()` → `get_node("Character",player_id).currency_balance` (`gold_poller.py:61-62`); quest status via `get_quest(quest_id).status` (`client.py:891-907`); treaty via a brokered-treaty read (does not exist — see Reachability).
Reachability: **B** (the *wealth* and *quest-chain* sub-paths are A — gold + quest pollers exist; the *treaty* sub-path needs an enabler: no `EngineClient` method calls `api/routes/treaties.py`, per D0 §2.7. Ship the faction OR wealth OR quest-chain win as A; add treaty later as B.)
Demo surface: `game_end_checker` delta below; `ObjectiveState` gains `win_path: Literal["faction","wealth","quests","treaty"] | None`; end overlay (`game_window.py:518-520`) keys its subtitle on `win_path` instead of only `arc_faction` — reuses the existing `ARC_WIN_SUBTITLES` dict pattern (`game_end_checker.py:31-42`) extended to a `WIN_PATH_SUBTITLES` map.
Content/seed: none for faction/wealth; quest-chain path reuses existing `aldric_deliver_quest` + chain-target quests (`seed.py:848-960`). A new `WIN_QUEST_CHAIN_IDS` constant lists the quest IDs that count.
Win/lose hook: add `WEALTH_WIN_THRESHOLD: int = 500`, `QUEST_CHAIN_WIN_COUNT: int = 3`, `WIN_QUEST_CHAIN_IDS: frozenset[str]`. New `check_win_multi(...)` returns True if `check_win(standings) OR (total_gold or 0) >= WEALTH_WIN_THRESHOLD OR len(completed & WIN_QUEST_CHAIN_IDS) >= QUEST_CHAIN_WIN_COUNT OR treaty_signed`. In `evaluate_game_end`, replace `elif check_win(standings)` (`:149`) with `elif check_win_multi(...)`, and record which predicate fired into `win_path`.
Prerequisite enablers: faction/wealth/quest = none; treaty sub-path depends on DEMO-D3-02-style route + a `get_active_treaties()` client method (route to D4/FEASIBILITY).
Effort: M   Player-value: high   Demo-fit: high
Risks / unknowns: balance — `WEALTH_WIN_THRESHOLD` must be reachable via trade but not trivially (tune vs `_PLAYER_STARTING_GOLD`, `seed.py:778`). Quest path needs the quest poller (DEMO-D3 has none today; reuse `get_quest` per-id, or add a small `QuestStatusPoller` mirroring `GoldPoller`).
First slice: faction-OR-wealth only (two A-paths, one new constant, one widened param). Quest + treaty land after.
Open questions: is the intended campaign "pick one path" or "any path"? → OPEN_QUESTIONS (D0 §1b guesses authored campaign, which favors distinct *signposted* paths).

---

### DEMO-D3-02: Resource/currency loop — gold as a win AND loss axis
Pillar: economy
Player fantasy: "My purse is the scoreboard: get rich enough to buy the town's safety, or go broke and watch it fall."
Why it matters: the currency engine is already surfaced across ~13 demo files (`gold_poller.py`, `ui/inventory_panel.py`, `ui/trade_panel.py`, the economy/trade route) yet currency touches the win/lose economy *zero* times today. Wiring gold into the end-state turns a decorative HUD number into a stake — high demo-fit (shows the engine's economy is *consequential*, moat §1a-4) at near-zero engine cost.
Current state: gold is polled (`gold_poller.py:57-67`) and shown in PLAYER STATUS / left panel (`game_window.py:419-421`) but never read by `game_end_checker` — `evaluate_game_end` has no gold parameter (`:120-125`).
Engine capability used: `GoldPoller.get_gold()` (`gold_poller.py:48-55`) → `currency_balance` on the player Character (`gold_poller.py:61-62`); `post_trade` (`client.py:1185`) is how the player moves gold.
Reachability: **A** — `GoldPoller` already runs in `game_window` (`game_window.py:419`); only plumbing `get_gold()` into `_poll_once` and into `evaluate_game_end` is needed. No new route.
Demo surface: `evaluate_game_end(..., total_gold=self._gold_poller.get_gold())` — but `game_end_poller` does not hold the `GoldPoller`; cleanest is to fetch gold inside `_poll_once` via the same `get_node("Character", player_id)` call (`gold_poller.py:61`). `ObjectiveState.total_gold` exposed so the end overlay can print the final purse. Optional: a `BANKRUPT` warning banner reusing the `EventBanner` widget (`widgets.py:445`).
Content/seed: none — `_PLAYER_STARTING_GOLD` already seeded (`seed.py:778`).
Win/lose hook: add `WEALTH_WIN_THRESHOLD: int = 500` and `BANKRUPTCY_LOSE_THRESHOLD: int = 0`. New `check_lose_bankrupt(total_gold: int | None) -> bool: return total_gold is not None and total_gold <= BANKRUPTCY_LOSE_THRESHOLD`. In `evaluate_game_end`, OR it into the lose branch: `if check_lose(iron_legion_controls) or check_lose_bankrupt(total_gold): outcome = "lose"` (`:147`). Wealth-win is the DEMO-D3-01 `WEALTH_WIN_THRESHOLD` predicate.
Win/lose hook caveat: bankruptcy must require the player to have *spent* (else they could start at 0). Gate with `_seen_positive_gold` latch in the poller (only arm bankruptcy after gold was once `> 0`), so the lose state is genuinely player-caused (over-bribing/over-trading), not a cold-start artifact.
Prerequisite enablers: none.
Effort: S   Player-value: high   Demo-fit: high
Risks / unknowns: bribing currently always *helps* standing and spends gold — must confirm bribe debits `currency_balance` so over-bribing can actually bankrupt (check `BribeScene`/trade path). Balance both thresholds vs starting gold.
First slice: bankruptcy lose only (one constant, one predicate, one OR into `:147`, plus the seen-positive latch). Wealth-win folds into DEMO-D3-01.
Open questions: should bankruptcy be instant-lose or a countdown ("3 ticks to recover")? → ties to DEMO-D3-04.

---

### DEMO-D3-03: Faction tension — gains with one faction COST another (zero-sum)
Pillar: economy
Player fantasy: "Every friend I make is an enemy I earn — I can't please everyone, so I must choose a side."
Why it matters: this is the mechanic that makes DEMO-D3-01's multiple paths *mutually exclusive* instead of "do all of them." It's the highest-leverage fix for D0 §4 ("distinct actions have no distinct consequences"): now allying merchants visibly *drops* thieves, so the win is a real choice. Sales-fit high — directly demonstrates reputation-as-state propagating tension, moat §1a-3.
Current state: `check_win` counts factions independently (`game_end_checker.py:98-103`); nothing reads cross-faction opposition. Standings only ever rise via bribes/quests.
Engine capability used: reputation already polled (`game_end_poller.py:104`); the tension itself is a **demo-side derived check** over the already-fetched `faction_standings` dict — no engine change needed for the *check*. (Whether the engine *itself* moves opposing standings on a bribe is a separate engine concern; the demo can at minimum *detect and gate* on the spread.)
Reachability: **A** for the detection/gate (pure function over `faction_standings` the poller already has). **B** only if we want the engine to actively decrement the opposed faction server-side (route to FEASIBILITY).
Demo surface: `evaluate_game_end` gains a tension guard: a multi-faction win is only awarded if the player did **not** also alienate a designated rival below a floor. `ObjectiveState.failure_reason` can carry `"overreach"`. No new UI required; POLITICS tab (`politics_panel.py:51`) already shows standings, making the tension legible.
Content/seed: a `FACTION_RIVALS` constant map (`merchants_guild`↔`thieves_guild`, `city_guard`↔`thieves_guild`) — pure constant, no graph seed. (If we want server-side decrement, that's an `OPPOSES`-edge seed = B.)
Win/lose hook: add `RIVAL_FLOOR: int = -25` and `FACTION_RIVALS: dict[str, str]`. New `check_overreach(standings) -> bool`: True if any qualified faction's rival is `< RIVAL_FLOOR`. Then in `check_win_multi`, the faction sub-path becomes `check_win(standings) and not check_overreach(standings)`. Alternatively make overreach a *lose* (`outcome="lose"`, `failure_reason="overreach"`) — a second distinct failure state (feeds DEMO-D3-05).
Prerequisite enablers: server-side rival decrement (the thing that makes the floor reachable through play) is the real dependency — without it the floor never trips. Either rely on existing bribe side-effects, or route an engine enabler to FEASIBILITY. Detection ships A regardless.
Effort: M (S for the check; M with the engine decrement enabler)   Player-value: high   Demo-fit: high
Risks / unknowns: if the engine never lowers a rival on a friendly action, the floor is inert (same trap as today's lose). Must confirm or enable the cross-faction debit, else this is cosmetic.
First slice: ship the `check_overreach` gate as a *win-blocker* (can't win the faction path while a rival is floored) — pure A. Promote to a lose state once the engine decrement is confirmed.
Open questions: does any current verb lower a faction's standing? If not, this needs an engine enabler before it bites → OPEN_QUESTIONS / FEASIBILITY.

---

### DEMO-D3-04: Time/tick pressure — a deadline via the clock
Pillar: economy
Player fantasy: "The Iron Legion marches at dawn — I have N days to rally the town or it falls."
Why it matters: converts the scripted, inert legion-lose into a *real* player-caused clock the player races against, giving the whole loop stakes and urgency (D0 §4). High demo-fit: showcases the consequential, auditable, tick-driven world (moat §1a-4) by making the clock *matter to the outcome*, not just advance events.
Current state: clock advances via `advance_clock` (`client.py:283-308`, driven by `SandboxLoop` auto-tick `sandbox_loop.py:79` or scripted `ClockTick`); `get_clock_state().current_tick` exists (`client.py:310-321`) but `game_end_checker` never reads tick — no deadline anywhere.
Engine capability used: `get_clock_state()` → `current_tick` (`client.py:310-321`); route `POST /v1/clock/advance` bounded `[1, MAX_DELTA_TICKS]` (`clock.py:37`). World epoch is also available via `WorldStatePoller.get_state()` (`world_state_poller.py:61-71`).
Reachability: **A** — `get_clock_state()` already exists on the client; add one call to `_poll_once` and one param to `evaluate_game_end`. No new route. (The demo has no clock *poller* yet, but `_poll_once` can call `get_clock_state()` directly, exactly as it already calls `get_graph_edges`.)
Demo surface: `evaluate_game_end(..., current_tick=self._client.get_clock_state().get("current_tick"))`. `ObjectiveState.ticks_remaining = DEADLINE_TICK - current_tick` exposed so `game_window` can render a countdown (reuse the status-overlay text path `game_window.py:472-488`, or a small banner). 
Content/seed: none — pure tick arithmetic.
Win/lose hook: add `DEADLINE_TICK: int = 40`. New `check_lose_deadline(current_tick, won_already) -> bool`: True if `current_tick is not None and current_tick >= DEADLINE_TICK and not won_already`. In `evaluate_game_end`, evaluate win *first* into a local `won` bool, then `if check_lose(...) or check_lose_deadline(current_tick, won): outcome="lose"` — i.e. the deadline only kills you if you have not already met any win path. (Note: this requires reordering so win is computed before the deadline-lose check, unlike today's lose-before-win at `:147-149`; document the reorder.)
Prerequisite enablers: a stable tick origin — DEADLINE must be relative to game start, not absolute, if the world isn't reset per session. Add `START_TICK` captured on first poll (latch in poller) and compare `current_tick - start_tick >= DEADLINE_TICKS`.
Effort: M   Player-value: high   Demo-fit: high
Risks / unknowns: in Free Play the clock only advances if auto-tick is ON (`sandbox_loop.py`) or the player manually ticks — a deadline is meaningless if the clock is frozen. Must either default auto-tick ON for timed mode or document the dependency.
First slice: relative-deadline lose with the `START_TICK` latch + an on-screen countdown; auto-tick defaulted ON.
Open questions: should the deadline be a hard lose or a "town weakened" soft penalty? → OPEN_QUESTIONS (ties to grade DEMO-D3-06).

---

### DEMO-D3-05: Multiple DISTINCT, player-reachable failure states (fix the inert lose)
Pillar: economy
Player fantasy: "I can lose in more than one way, and each loss is on me — bankruptcy, overreach, or running out of time."
Why it matters: this is the literal D0 §4 fix — replace the one scripted, player-inert lose with ≥2 reachable, player-caused failures. Without it the demo has stakes only on the win side. Highest player-value-per-effort because it composes the lose hooks already specified in D3-02/03/04.
Current state: exactly one lose, `check_lose(iron_legion_controls)` (`game_end_checker.py:106-117`), structurally unreachable by the player (`:24-26` comment; D0 §2.1). `evaluate_game_end` `:147` is the only lose branch.
Engine capability used: composes the already-cited pollers — gold (`gold_poller.py:61`), clock (`client.py:310`), reputation (`game_end_poller.py:104`).
Reachability: **A** for the bankruptcy + deadline failures (data already polled / one client call); **B** for the overreach failure *biting* (needs the cross-faction decrement from D3-03). Ship 2 A-failures now; overreach is the third when the engine enabler lands.
Demo surface: `evaluate_game_end` collects all lose predicates and sets `ObjectiveState.failure_reason: Literal["legion","bankruptcy","deadline","overreach"] | None`. End overlay (`game_window.py:521-524`) selects the DEFEAT subtitle by `failure_reason` via a new `LOSE_SUBTITLES` map (mirrors `ARC_WIN_SUBTITLES` `:31-42`) instead of the hardcoded Iron-Legion string at `:522`.
Content/seed: none beyond the constant maps from D3-02/04 (+ D3-03 rivals if/when enabled).
Win/lose hook: replace the single lose line `:147` with:
```python
failure = (
    "legion" if check_lose(iron_legion_controls)
    else "bankruptcy" if check_lose_bankrupt(total_gold)
    else "deadline" if check_lose_deadline(current_tick, won)
    else "overreach" if check_overreach(standings)   # B, when enabled
    else None
)
outcome = "lose" if failure else ("win" if won else None)
```
with `ObjectiveState.failure_reason=failure`. Preserves the "lose beats win" tie-break (D0 §2.1) by checking failures before assigning win.
Prerequisite enablers: DEMO-D3-02 (bankruptcy hook), DEMO-D3-04 (deadline hook); DEMO-D3-03 for overreach (B).
Effort: S (pure composition once 02/04 land)   Player-value: high   Demo-fit: med (failure variety is great game-feel; only overreach/legion are *engine-specific* showcases, bankruptcy/deadline are generic).
Risks / unknowns: ensuring exactly one `failure_reason` wins when several fire at once (ordered if-chain above makes it deterministic — document the priority).
First slice: wire bankruptcy + deadline as the two reachable failures with `failure_reason` + `LOSE_SUBTITLES`. That alone satisfies "≥2 distinct player-caused failures."
Open questions: failure priority order when multiple co-fire (legion > bankruptcy > deadline > overreach assumed) → confirm with human / OPEN_QUESTIONS.

---

### DEMO-D3-06: Score / grade at the end (S/A/B/C) instead of binary win/lose
Pillar: economy
Player fantasy: "I didn't just win — I won with an S-rank: three factions, full coffers, peace signed, days to spare."
Why it matters: a grade gives a *reason to replay* even after you can win (D0 §1b replayability gap) and turns the multi-axis economy into a single legible scoreboard that rewards mastering *all* paths, not just clearing one. Demo-fit med-high: a graded end-card is a strong sales-artifact closer ("look how much state the engine tracked") even though grading itself is generic.
Current state: outcome is binary `Literal["win","lose"] | None` (`game_end_checker.py:59`); the end overlay shows only VICTORY/DEFEATED + a subtitle (`game_window.py:510,518-524`). No score anywhere.
Engine capability used: aggregates the already-polled axes — `faction_standings` (`game_end_poller.py:104`), `total_gold` (`gold_poller.py:61`), `ticks_remaining` (D3-04), completed quests (`get_quest`, `client.py:891`).
Reachability: **A** — pure function over data the other specs already plumb into `evaluate_game_end`; no new fetch beyond what 01/02/04 add.
Demo surface: `ObjectiveState.grade: Literal["S","A","B","C"] | None`, set only when `outcome=="win"`. End overlay (`game_window.py:509-515`) renders the letter beside "VICTORY!" using the existing `FontLoader.get(36)` headline path. Optional breakdown lines (factions/gold/ticks) reuse `FontLoader.get(16)` sub-text (`:517`).
Content/seed: none.
Win/lose hook: add a pure `compute_grade(standings, total_gold, ticks_remaining, completed_quest_ids) -> Literal["S","A","B","C"]` with `GRADE_*` weight/threshold constants (e.g. `GRADE_S_MIN_SCORE: int = 90`). Called at the end of `evaluate_game_end` when `outcome=="win"`; stored on `ObjectiveState.grade`. No change to the win/lose *trigger* — purely additive to the win branch.
Prerequisite enablers: most valuable after DEMO-D3-01/02/04 land (so the score has multiple axes); ships standalone over faction-standing alone if needed.
Effort: M   Player-value: med (replay incentive, not new agency)   Demo-fit: med-high
Risks / unknowns: grade-curve tuning is pure balance work; risk of an always-S or always-C curve if thresholds aren't playtested. Pygame: rendering one extra glyph + 3 lines is trivial (proven overlay path).
First slice: grade off faction-standing sum alone (S = all 3 ≥ 50, A = 2 high + 1 mid, etc.), one `compute_grade`, one `ObjectiveState` field, one overlay line. Add gold/time axes as they land.
Open questions: weighting across axes (is wealth worth as much as factions?) → OPEN_QUESTIONS / balance pass.

---

## 3. Cross-references
- Builds on **D0 (`DEMO_INTENT.md`)** §2.1 (current win/lose table), §2.5 (poller pattern),
  §3 (rubric), §4 (verdict — the multi-objective + reachable-failure mandate).
- Feeds **D4 (`FEASIBILITY.md`)**: the type-B enablers here are (a) a brokered-treaty read
  (`get_active_treaties()` client method over `api/routes/treaties.py`, D0 §2.7) for the
  D3-01 treaty win path, and (b) a server-side cross-faction standing decrement for D3-03's
  overreach to *bite*. Everything else is type-A.
- Feeds **D5 (`DEMO_EXPANSION_ROADMAP.md`)**: Phase-1 candidates are the type-A, high-value,
  high-fit items — D3-02 (S, A), D3-04 (M, A), D3-05 (S, A, composes 02+04). D3-01 faction/
  wealth/quest sub-paths (A) before its treaty sub-path (B). D3-06 grade after the axes exist.

---

## 4. Summary (6 lines)
1. **Multi-objective win (D3-01):** faction-standing **OR** wealth (`gold ≥ 500`) **OR** quest-chain (3 of N) **OR** brokered treaty — faction/wealth/quest are **type-A**, treaty is **type-B** (needs `get_active_treaties()` over `treaties.py`).
2. **Currency loop (D3-02):** gold becomes both a win axis (`WEALTH_WIN_THRESHOLD=500`) and a loss axis (`BANKRUPTCY_LOSE_THRESHOLD=0`, armed only after gold was once positive) — **type-A** (`GoldPoller` already runs).
3. **Faction tension (D3-03):** a `RIVAL_FLOOR` overreach check blocks the faction win when a rival faction is floored — detection is **type-A**, but it only *bites* with a server-side cross-faction decrement (**type-B**).
4. **Time pressure (D3-04):** relative `DEADLINE_TICKS` from a latched `START_TICK` via `get_clock_state().current_tick` — lose if undone by the deadline — **type-A** (one client call), needs auto-tick ON.
5. **Distinct failures (D3-05):** ≥2 reachable, player-caused losses — **bankruptcy** and **deadline** ship **type-A** now (plus the inert legion retained); **overreach** is the third when D3-03's enabler (type-B) lands; `failure_reason` drives a `LOSE_SUBTITLES` end-card.
6. **End grade (D3-06):** pure `compute_grade(...) → S/A/B/C` over the already-plumbed axes, additive to the win branch — **type-A**.
