# EVAL-P20.2 — capability-case review sheet

Nine `case_pos_*` cases, one for each NPC that was in `UNCOVERED_BASELINE`.

**Status: promoted.** All nine were accepted as drafted and moved to `evals/cases/`;
`UNCOVERED_BASELINE` is now empty. This sheet is kept as the authoring record — what was
proposed, what was checked, and what it measured. The draft YAMLs are gone because they
would be byte-duplicates of the promoted cases.

## Verification already run on every row

| Check | What it means | Result |
|---|---|---|
| **echo** | the case is scored against an echo of its own `player_message` | must FAIL |
| **hedge** | the case is scored against the reference always-hedge responder (`scripts/hedge_responder_probe.py::CANNED_HEDGE`) | must FAIL |

Both are mechanical: `keyword_any` tokens are drawn from the *grounded fact's* text and are
absent from the player prompt, so a response that only reflects the question back scores nothing.

## Candidates

| # | NPC | Grounding edge | Proposed player message | Proposed expectation (`keyword_any`) | echo | hedge |
|---|---|---|---|---|---|---|
| 1 | `bren_smith` | BELIEVES(bren_smith, bel_bren_smith_10b4fcfc) + REMEMBERS(bren_smith, mem_bren_smith_0) | "You don't look pleased, Bren. Is the forge doing all right this season?" | `tithe`, `third`, `protection`, `contract`, `captain`, `pay`, `coin`, `guard` | FAILS (good) | FAILS (good) |
| 2 | `dorn_dockmaster` | BELIEVES(dorn_dockmaster, bel_dorn_dockmaster_1a330af7) | "They tell me nothing moves through this harbour without you knowing. How do you keep it all straight?" | `manifest`, `ledger`, `paper`, `book`, `head`, `memory`, `crate`, `cargo`, `record` | FAILS (good) | FAILS (good) |
| 3 | `garrick_deserter` | BELIEVES(garrick_deserter, bel_garrick_deserter_b070850f) + REMEMBERS(garrick_deserter, mem_garrick_deserter_0) | "You've the look of a man who's been somewhere bad. What did you see out there?" | `legion`, `prisoner`, `village`, `town`, `burn`, `march`, `soldier`, `officer`, `army` | FAILS (good) | FAILS (good) |
| 4 | `harwick_guard` | BELIEVES(harwick_guard, bel_harwick_guard_71e419d6) + REMEMBERS(harwick_guard, mem_harwick_guard_0) | "Anything about the way things are being run that's been sitting badly with you?" | `gate`, `sergeant`, `south`, `posting`, `orders`, `captain`, `watch`, `patrol`, `bribe` | FAILS (good) | FAILS (good) |
| 5 | `nel_pickpocket` | BELIEVES(nel_pickpocket, bel_nel_pickpocket_77ebc2b0) + PURSUES(nel_pickpocket, goal_nel_pickpocket_0) | "Who's keeping you busy these days, Nel? You've the air of someone with somewhere to be." | `lira`, `test`, `job`, `guild`, `prove`, `fence`, `market`, `purse`, `lift` | FAILS (good) | FAILS (good) |
| 6 | `nessa_priestess` | PURSUES(nessa_priestess, goal_nessa_priestess_0) + BELIEVES(nessa_priestess, bel_nessa_priestess_9bfffc52) | "Everyone in this city seems certain they're the ones in the right. Where do you stand?" | `neutral`, `temple`, `faction`, `dying`, `wounded`, `both`, `confession`, `righteous`, `tend` | FAILS (good) | FAILS (good) |
| 7 | `sera_barmaid` | REMEMBERS(sera_barmaid, mem_sera_barmaid_0) + BELIEVES(sera_barmaid, bel_sera_barmaid_7726faab) | "You're behind that counter every evening. Does much get past you?" | `note`, `lira`, `hooded`, `drink`, `listen`, `remember`, `cup`, `ledger`, `second`, `tongue` | FAILS (good) | FAILS (good) |
| 8 | `tilda_herbalist` | PURSUES(tilda_herbalist, goal_tilda_herbalist_0) | "Is there anything you're short of at the stall just now?" | `northwood`, `bark`, `supply`, `herb`, `remedy`, `pain`, `route`, `root`, `physic` | FAILS (good) | FAILS (good) |
| 9 | `vex_spymaster` | PURSUES(vex_spymaster, goal_vex_spymaster_0) + BELIEVES(vex_spymaster, bel_vex_spymaster_4fd4429b) | "You've been in this city a long while, Vex. What is it you're actually working toward?" | `accord`, `treaty`, `merchant`, `guard`, `leverage`, `crown`, `negotiat`, `legion`, `terms`, `broker` | FAILS (good) | FAILS (good) |

Every case also carries `- kind: schema` and a `relevant_node_ids` annotation.

## `relevant_node_ids` per candidate

| NPC | relevant_node_ids |
|---|---|
| `bren_smith` | `bren_smith`, `bel_bren_smith_10b4fcfc`, `mem_bren_smith_0`, `city_guard`, `loc_forge` |
| `dorn_dockmaster` | `dorn_dockmaster`, `bel_dorn_dockmaster_1a330af7`, `loc_docks`, `merchants_guild` |
| `garrick_deserter` | `garrick_deserter`, `bel_garrick_deserter_b070850f`, `mem_garrick_deserter_0`, `iron_legion`, `loc_tavern` |
| `harwick_guard` | `harwick_guard`, `bel_harwick_guard_71e419d6`, `mem_harwick_guard_0`, `city_guard`, `loc_guard_barracks` |
| `nel_pickpocket` | `nel_pickpocket`, `bel_nel_pickpocket_77ebc2b0`, `goal_nel_pickpocket_0`, `lira_fence`, `thieves_guild` |
| `nessa_priestess` | `nessa_priestess`, `goal_nessa_priestess_0`, `bel_nessa_priestess_9bfffc52`, `mem_nessa_priestess_0`, `loc_temple` |
| `sera_barmaid` | `sera_barmaid`, `mem_sera_barmaid_0`, `bel_sera_barmaid_7726faab`, `lira_fence`, `loc_tavern` |
| `tilda_herbalist` | `tilda_herbalist`, `goal_tilda_herbalist_0`, `bel_tilda_herbalist_3ee3fd1c`, `loc_market_square` |
| `vex_spymaster` | `vex_spymaster`, `goal_vex_spymaster_0`, `bel_vex_spymaster_4fd4429b`, `crown_loyalists`, `loc_guard_barracks` |

## What this measured

**Hedge gate** (`make hedge-probe`, EVAL-P20.2 validation 2):

| Set | Rate | Verdict |
|---|---|---|
| the 9 cases above | **0/9 = 0.000** | GATE MET |
| whole battery (16 cases) | **6/16 = 0.375** | GATE NOT MET — the 6 legacy cases are the floor (ISSUE-146) |

**Live engine run**, all 9 against `POST /v1/dialogue` on 2026-08-10: **2/9 pass**
(`dorn_dockmaster`, `tilda_herbalist`, both on generic domain words rather than on their
grounded fact). The seven failures are not authoring defects — the dialogue context
arrives with no beliefs, goals, memories or profile in it for *any* NPC, so there is
nothing for the model to surface. Asked about his own forge, `bren_smith` replied
*"I've heard the blacksmiths are struggling a bit this spring"* — third person, about
himself. That is **ISSUE-145**, filed P1 for hand review.

For contrast, the seven legacy cases score 6/6 live, but every response is a variant of
*"Word travels fast around here, stranger... the northern war rages on"*, passing only
because their keyword lists contain `war`/`north`/`heard`. Same mechanism as the hedge.

---

Generated for EVAL-P20.2. See `docs/CAPABILITY_CASES.md` for the authoring contract.
