# CR-L01 — Engines lens (engines/, services/, retrieval/, graph/, scheduler/)

Branch `eval-ab-context-arms`, HEAD d46ae42. Live API at `http://127.0.0.1:8000` used for
read-only confirmation (auth: `Authorization: Bearer $API_KEY_SECRET`; the `X-API-Key`
header is *not* accepted — `auth/api_key.py:23`). No file in the repo was modified.

---

## Required measurements

### 1. Fallback contract wired at the call site?

**Selection method.** The 5 engines CLAUDE.md names (dialogue, gossip, emotion, quest, tick
scheduler) + the 8 largest `engines/` subpackages by LOC excluding `ports/` (protocols only)
+ 5 tick engines chosen to span LLM-calling / graph-only / service-delegating shapes. 18 rows.

**Not reached at depth (21 packages, 4,462 LOC):** agenda, clique, currency, deception,
director (partial only), economy, faction_politics, idempotency, investigation,
knowledge_learning, memory, mood, need, oath, planning, player_model, relationship, routine,
scheming, story_pacing, succession, treaty, tts.

CLAUDE.md's two contracts: **(G)** Neo4j unavailable → `GraphUnavailableError` → API 503;
**(L)** LLM timeout → serve `fallback_responses.json`.

Baseline facts, re-verified this session:

```
$ grep -rn "raise GraphUnavailableError" src/           → 0
$ grep -rn "except.*GraphUnavailableError" src/         → 0
$ grep -rn "raise TokenBudgetExceededError" src/        → 0
$ grep -rn "503" src/npc_engine/api/ --include=*.py     → 0
```

| # | Engine (LOC) | Documented fallback (quoted) | Wired at call site? | Verdict |
|---|---|---|---|---|
| 1 | dialogue (1917) | `llm_client.py:85` "Returns a deterministic fallback dict on LLMTimeoutError, LLMRequestError" | **G:** no — `degradation.py:107,119` bare `except Exception` turns a Neo4j outage into a canned 200. **L:** yes — `dialogue_handler.py:179` → `llm_client.py:102,105,246` → `_load_fallback_dialogue` | L wired, G **inverted** |
| 2 | gossip (1265) | none declared | `gossip_handler.run_tick` has no graph `except`; `_run_side_effects:333` `except Exception: LOGGER.exception(...); raise` → swallowed by `tick_scheduler.py:239` | unwired |
| 3 | quest / lifecycle (1264) | `quest_lifecycle_engine.py:93` "Best-effort — skips on error." | `:105 except Exception:` warn + `return` — only for commitment memory. Graph errors elsewhere propagate to `api/errors/exception_handlers.py:122` catch-all → **500** | unwired (G) |
| 4 | emotion (815) | none declared | `emotion_updater.py:167` `if self._writer is not None:` — a missing writer silently no-ops the graph write-through | unwired |
| 5 | tick scheduler (1190) | `tick_scheduler.py:224` "logs `tick_engine_error`, records the error, and returns None … without killing the loop" | wired at `:239-246` and `:386-389` — **this is the only fallback in the tick path, and it is a catch-all** | wired, but see F-10 |
| 6 | interaction (1176) | none declared | `quest_handler.py:158` `except Exception: _logger.warning("update_objective failed …")` — objective silently not advanced | unwired |
| 7 | llm adapters (1140) | `openai_adapter.py:12` "on timeout raises LLMTimeoutError; on transport/parse failure raises LLMRequestError" | raises correctly (`ollama_adapter.py:105,173,259`); **only 2 files in all of `engines/` catch these** (`dialogue/llm_client.py`, `quest_generation/quest_generation_engine.py`) | raise wired, catch 2/N |
| 8 | quest_generation (1139) | `:284` docstring absent; code returns `{}` | `:284 except (LLMTimeoutError, LLMRequestError): return {}` and `:324 → return default_description`. Does **not** use `fallback_responses.json` | partially wired, silent |
| 9 | proactive_dialogue (779) | `proactive_engine.py:187` "LLMTimeoutError: If the LLM backend times out." | `proactive_tick_adapter.py` contains **zero** `except` — propagates to `_run_engine_safe` → swallowed | unwired |
| 10 | events (405) | none declared | no `except`; `run_tick` also `return {"created": 0}` at `event_handler.py:171` with no log | unwired |
| 11 | chapter (381) | `chapter_engine.py:274` "LLM chapter labeling failed … using rule-based fallback" | wired: `:272 except Exception:` → `label_chapter_by_rules(...)`. Does not use `fallback_responses.json` | wired (own corpus) |
| 12 | reputation (381) | `reputation_engine.py:114` "skip silently if edge missing or standing too low" | `:121,:155,:164 except RelationEdgeNotFoundError: return` — three silent exits | wired-as-silent |
| 13 | military (413) | `military_battle_service.py:59` "**Fallback: Neo4j unavailable → raises GraphUnavailableError (propagated to engine).**" | **Nothing raises `GraphUnavailableError` anywhere in `src/`.** `military_engine.py` has no `except`. The promised exception cannot occur | **unwired — docstring is fiction** |
| 14 | military resources | `military_resource_service.py:47` same sentence | same | **unwired — fiction** |
| 15 | memory_consolidation (236) | `:137` "LLM error during consolidation … skipping" | `:137 except Exception: return None`; `:153` swallows the witnessed query. **Engine is never wired into the scheduler at all** — see F-03 | dead on tick path |
| 16 | skill_progression (87) | none | `skill_progression_engine.py:71 except Exception: _LOGGER.exception(...)` — XP silently not awarded | unwired |
| 17 | context assembly (`retrieval/context`) | CLAUDE.md: "`context_builder.py` raises `TokenBudgetExceededError` if Tier 0 + Tier A alone exceed `config.PROMPT_TOKEN_BUDGET`" | Never raised. `context_budget_enforcer.py:348 except ContextBudgetError: return []` drops a whole tier; `:366-373` can return an **over-budget** prompt | **unwired — see F-06** |
| 18 | `dialogue_graph_port` (contract surface) | `ports/dialogue_graph_port.py:73` "GraphUnavailableError: If Neo4j is unreachable." | no implementor raises it (`graph/repositories/dialogue_repository.py` lets `neo4j.exceptions.*` through) | **unwired — fiction** |

**Verdict: 18 traced / 4 wired as documented (dialogue-L, tick scheduler, chapter, reputation) /
14 unwired.** Four of the 14 (#13, #14, #17, #18) have docstrings that *promise* behaviour the
codebase cannot produce.

### 2. Engines whose failure path is untested

Method: for each engine in the sample, locate the specific `except`/fallback line, then grep
`tests/` for the log key, the error type, or a failure-injecting mock reaching that branch, and
read the test. A test that asserts a constant, or that would still pass with the fallback
deleted, counts **untested**.

| Engine | Failure branch | Test that drives it | Untested? |
|---|---|---|---|
| dialogue (LLM) | `llm_client.py:102,105` | `tests/unit/engines/test_dialogue_handler_fallback_v14.py` — injects a raising LLM | tested |
| dialogue (graph→canned) | `degradation.py:119` | none drives a graph failure through `handle()`; `test_dialogue_retrieval_profile.py:71` is a **source-string assertion** (F-05) | **untested** |
| tick scheduler isolation | `:239` | `test_tick_scheduler_engine_isolation.py:89-179` (`_ThrowingEngine`) — covers gossip, event, story_pacing, faction_politics only (4 of 27 slots) | 4/27 tested |
| gossip | `_run_side_effects:333` re-raise | grep `create_rumor` failure injection in `tests/` → none | **untested** |
| emotion | `_write_through` writer-None | no test asserts the writer is present in the composition root | **untested** |
| quest lifecycle | `:105` `commitment_memory_skipped_no_world_state` | `grep -rl "commitment_memory_skipped" tests/` → **empty** | **untested** |
| interaction | `quest_handler.py:158` | `grep -rn "update_objective failed" tests/` → none | **untested** |
| quest_generation | `:284,:324` | `test_quest_generation_engine.py` injects LLM errors | tested |
| proactive_dialogue | no branch exists | n/a — nothing to test | **untested (no path)** |
| events | `:171 created:0` | `test_gossip_event_selection.py` covers selection, not the empty-location exit | **untested** |
| chapter | `:272` | `test_chapter_engine.py` asserts `label_chapter_by_rules` | tested |
| reputation | `:121,155,164` | `test_reputation_engine.py` references `RelationEdgeNotFoundError` | tested |
| military | none | n/a | **untested (no path)** |
| memory_consolidation | `:137,:153` | `test_memory_consolidation_engine.py` | tested; **but the engine never runs (F-03)** |
| skill_progression | `:71` | `test_skill_progression_engine.py` — no raising repo | **untested** |
| context budget | `:348 except ContextBudgetError` | `test_context_budget_enforcer_v14.py:375-384` asserts fill_to_budget *raises* only for tier0; nothing asserts the tier-drop path | **untested** |
| context over-budget | `:370 if not droppable: break` | none | **untested** |

**Count: 11 of 17 sampled failure paths are untested** (two of which have no failure path at
all to test). The tick-isolation contract is tested for 4 of 27 engine slots.

### 3. Where a bug would be silent

`except` blocks in `engines/ services/ retrieval/ scheduler/ graph/` whose body contains no
`raise` (mechanical scan, script kept in scratch): **66 sites**. Worst 10 by consequence:

| Rank | Site | Why it is silent | Consequence |
|---|---|---|---|
| 1 | `scheduler/tick_scheduler.py:239` (+`:386`) | catch-all `except Exception` around every one of 27 engines | The entire world simulation can be dead and `POST /v1/clock/advance` still returns **200** with empty per-engine lists. Only `GET /v1/admin/system/engines` reveals it, and only if a store is injected |
| 2 | `retrieval/context/context_budget_enforcer.py:348` | `except ContextBudgetError: return []` | A whole context tier vanishes from the prompt; the NPC just sounds less informed |
| 3 | `retrieval/context/context_budget_enforcer.py:366-373` | `while … if not droppable: break` | Returns an **over-budget** prompt with no error and no metric; Ollama silently truncates it |
| 4 | `engines/dialogue/degradation.py:107` and `:119` | bare `except Exception` twice | Neo4j outage, `RetrievalProfileNotFoundError`, `ContextBudgetError`, and a genuine bug all collapse to the same canned 200 (F-04) |
| 5 | `engines/interaction/quest_handler.py:158` | `except Exception: _logger.warning("update_objective failed …")` | Quest objective never advances; the quest cannot be completed and nothing surfaces |
| 6 | `engines/skill/skill_progression_engine.py:71` | `except Exception: _LOGGER.exception(...)` | XP silently not awarded; progression quietly stops |
| 7 | `engines/quest/quest_lifecycle_engine.py:105` | warn + `return` | Accepted quests form no commitment memory; the NPC has no recollection of the deal |
| 8 | `engines/quest_generation/quest_generation_engine.py:284` | `return {}` | A quest is generated with **empty slots** rather than not generated |
| 9 | `graph/graph_reader.py:214` | `except Exception: return value` | Any coercion failure returns the raw value; malformed graph data reaches the prompt untyped |
| 10 | `retrieval/embedding/embedding_reconciler.py:154` | `except Exception: LOGGER.exception(...); await asyncio.sleep(...)` | The reconciler loops forever on a permanent failure; embeddings drift with no alarm |

**Defaults substituted for missing domain-critical data** (`.get(field, default)` — 30 sites):
`engines/gossip/gossip_handler.py:227 int(sharer.get("honesty", 50))` is the worst: `honesty`
feeds *both* the distortion probability and the SHA-256 seed (`gossip_distort.py:99-112`), so a
Character node missing `honesty` silently changes gossip determinism rather than failing.
`engines/gossip/pair_selector.py:24 character.get("gossipy", 50)` silently equalises pair
ranking. In Cypher, `graph/gossip/gossip_batch_queries.py:46 coalesce(r.trust, 50)` makes "no
RELATES_TO edge" indistinguishable from "neutral trust".

**Empty-list / zero returns indistinguishable from failure:** `event_handler.py:171`
(`created: 0` with no log), `gossip_batch_queries.py:113-114` (`if not pairs: return []`),
`context_budget_enforcer.py:348` (`return []`), `quest_generation_engine.py:284` (`return {}`).

**Silent clamping in probability code:** `gossip_distort.py:76`
(`max(0.0, min(1.0, …))`), `:218` (`min(1.0, probability * hostile_distortion_factor)`),
`:241` (`min(100, max(1, int(probability * 100)))`), `:96` (`min(100, max(1, …))`). Each clamp
is legitimate individually; none logs when it binds, so a mis-tuned
`GOSSIP_DISTORTION_BASE` that saturates to 1.0 for every pair is invisible.

### 4. The LLM-timeout half of the contract

`src/npc_engine/data/fallback_responses.json` **exists** (6 archetype keys + `default`).

```
$ grep -rn "LLM_FALLBACK_PATH\|fallback_responses" src/ --include=*.py
src/npc_engine/config.py:106:    LLM_FALLBACK_PATH: str = "data/fallback_responses.json"
src/npc_engine/config.py:448:    @field_validator("LLM_FALLBACK_PATH")
src/npc_engine/engines/dialogue/dialogue_handler.py:179:            fallback_path=self._settings.LLM_FALLBACK_PATH,
```

**Exactly one call site.** It is genuinely wired: `dialogue_handler.py:179` →
`DialogueLLMClient.__init__` → `llm_client.py:102/105` (`generate_response`), `:246`
(`stream_text`), `:429` (`ValidationError` in `_run_llm_pipeline`). This half of the contract is
real for dialogue.

It is wired for **nothing else**. The other LLM-calling engines have their own private fallback
corpora or none at all:

- `chapter_engine.py:274` → `label_chapter_by_rules` (rule-based, not the JSON).
- `quest_generation_engine.py:284/:324` → `{}` / `default_description`.
- `memory_consolidation_engine.py:137` → `None`.
- `proactive_engine.py:187` documents `LLMTimeoutError` and **nothing catches it**.
- `degradation.py:32-46` reads a *third* corpus (`CANNED_RESPONSES_DIR/*.yaml`) and hardcodes
  `return "I need a moment to think."` at `:46` — byte-identical to
  `fallback_responses.json`'s `default[0]`, maintained in two places.

### 5. Token budget enforcement

`TokenBudgetExceededError` is `class TokenBudgetExceededError(Exception)` at
`utils/errors.py:301` — a bare `Exception`, and **it is imported by nothing**. Across all of
`src/` it is neither raised, caught, nor referenced; the only live mentions are
`docs/PROMPT_DESIGN.md:91` and `project-harness/archive/`.

What the code actually does when the budget is exceeded, on the shipped path
(`context_builder.py:575` → `fill_to_budget_with_report`):

- `context_budget_enforcer.py:213-217` and `:266-269`: non-fitting items are `continue`d — dropped.
- `:348`: `except ContextBudgetError: return []` — a whole compressible tier is dropped.
- `:366-373`: if the *serialized* prompt is still over budget and nothing droppable remains,
  the loop `break`s and returns the over-budget prompt.
- The only surviving raise sites are `enforce_context_budget` (`:74-88`), which the production
  path never calls — `grep` shows callers only in `__init__.py` re-exports and unit tests.

Drops are recorded on a `BudgetFillReport` and attributed by `_attribute_drops` (`:378-405`), so
the data exists — but nothing on the dialogue path raises, logs at WARNING, or fails a turn.

**The 2026-08-27 fix (`96d83eb`) is real, and its guard is a frozen snapshot, not a live check.**
The commit raises `OLLAMA_CONTEXT_LENGTH` 8192 → 12288 (budget 1062 → 5158) and re-sizes tier
ceilings, and the new test compares the shipped default against *measured demand* rather than
against the window — which is a genuine improvement over `TestShippedDefaultsAreCoherent`, whose
`system + budget + output + headers <= window` is satisfied by construction because the budget is
derived as `window - overhead`. Two caveats:

1. `MEASURED_ROSTER_CEILING_TOKENS = 1151` and `MEASURED_TIER_MAXIMA` (`:45-54`) are hand-copied
   constants from one run. Nothing re-measures them. If an engine adds a tier-A slot tomorrow,
   demand rises, the constants do not, and the test still passes while items are dropped again —
   exactly the ~2.5-month failure mode it was written to end.
2. `test_the_derived_budget_is_the_window_minus_the_named_overhead` (`:104-106`) **is
   tautological**: it asserts `_code_default_budget() == window - PROMPT_WINDOW_OVERHEAD_TOKENS`,
   and `_code_default_budget()` is *defined* at `:75` as `max(MIN, window - overhead)`. It
   restates its own helper and can only fail if the 512-token floor binds. The other five
   assertions are substantive.

### 6. Gossip distortion chain correctness

**Seeded and logged?** Yes for distortion: `compute_seed_value` = `int(sha256(f"{summary}|{honesty}|{trust}|{tick_id}")[:8], 16)`
(`gossip_distort.py:99-112`), logged at DEBUG with the probability at `gossip_handler.py:243-251`
and returned in `run_tick`'s `seeds_used`. Secret propagation seeds are logged at
`gossip_handler.py:388-391`. **Event sampling is not**: `event_handler.py:129
rng = self._rng or random.Random(tick_id)` logs nothing, violating the same rule gossip honours.
Pair selection uses no RNG (deterministic sort), so nothing to log there.

**Does 2-hop distortion compound? No — CONFIRMED, live.** Traced chain:
`gossip_handler.py:170` `select_batch_event_trust` →
`graph/repositories/gossip_repository.py:80` →
`graph/gossip/gossip_batch_queries.py:29-47`, which returns `best_event.summary` — the
**canonical `Event` node property** — and never `k.distorted_summary` from the sharer's own
`KNOWS_ABOUT` edge. `gossip_handler.py:257` then feeds `str(row["summary"])` into
`gossip_distort`. The receiver's distorted text is written at `gossip_batch_queries.py:60` and
read back only by `graph_reader.py:33`, `rumor_trace_service.py:27` and
`reputation_queries.py:46` — for *prompt display*, never as a gossip source.

Live proof (read-only, `GET /v1/graph/edges/KNOWS_ABOUT?dst_id=northern_war_begins`):

```json
{"src_id":"captain_sorn",   "knowledge_state":"knows","distortion_level":0,
 "distorted_summary":"The northern armies have crossed the border. We are at war."}
{"src_id":"mira_innkeeper", "distortion_type":"exaggeration","source_character_id":"captain_sorn",
 "learned_at_tick":1,"distortion_level":20,
 "distorted_summary":"A soldier passing through told me the northern armies, the Iron Guard he called them, have moved on the border. …"}
{"src_id":"lira_fence",     "distortion_type":"omission","source_character_id":"mira_innkeeper",
 "learned_at_tick":10,"distortion_level":62,"distorted_summary":"The northern armies"}
{"src_id":"aldric_merchant","distortion_type":"role_swap","source_character_id":"tilda_herbalist",
 "learned_at_tick":600,"distortion_level":74,
 "distorted_summary":"They say the opposite happened: The northern armies have crossed the border"}
{"src_id":"old_henryk",     "source_character_id":"aldric_merchant","learned_at_tick":600,
 "knowledge_state":"knows","distortion_level":0,
 "distorted_summary":"The northern armies have crossed the border"}
```

`lira_fence` learned from `mira_innkeeper`, whose account is the 27-word "A soldier passing
through told me…". Omission halves the words of its input. Lira's stored text is
`"The northern armies"` — exactly `omission("The northern armies have crossed the border")`,
i.e. half of the **canonical 7-word event summary**, not half of Mira's account. Same for
`tilda_herbalist` (learned from `old_henryk`) and for `aldric_merchant`, whose role_swap prefix
sits on the canonical string. Every hop distorts the original.

**Would a test catch distortion becoming a no-op?** Partly, and not the compounding.
`tests/unit/engines/test_gossip_distort.py:48` asserts `distortion_type is not None` for one
hostile input and `:70` asserts the canonical passthrough — but **no test in the repo asserts
`result.summary != event_summary`**. If `exaggeration`/`role_swap`/`timeline_shift` returned
their input unchanged, `test_gossip_distort.py`, `test_gossip_determinism.py` and
`test_gossip_distortion_sev36.py` all still pass; only
`tests/unit/config/test_prefix_loader.py:17` (`"catastrophic" in prefix.lower()`) and the three
`test_distortion_strategy_registry.py` parity tests would catch it, and those test the
strategies in isolation, never through `gossip_distort` or the handler. **No test asserts
multi-hop behaviour at all.**

---

## Findings

### [CR-L01-01] Make gossip distortion compound across hops — today every hop distorts the original event

- **Severity:** CRITICAL
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** Traced chain: `engines/gossip/gossip_handler.py:170` → `graph/repositories/gossip_repository.py:80` → `graph/gossip/gossip_batch_queries.py:29-47`, which returns `best_event.summary` (the canonical `Event` node) and never `k.distorted_summary`; `gossip_handler.py:257` passes `str(row["summary"])` to `gossip_distort`. Live, read-only: `lira_fence` learned `northern_war_begins` from `mira_innkeeper` (whose stored account is 27 words) yet holds `"The northern armies"` = `omission("The northern armies have crossed the border")` — half of the canonical 7-word summary. `aldric_merchant`'s role_swap prefix likewise sits on the canonical string, not on `tilda_herbalist`'s account. See §6 for the full JSON.
- **Cost of inaction:** The project's signature demo — "gossip mutates as it travels, `captain_sorn` → `mira_innkeeper` → `old_henryk`" — is a claim the engine does not implement. Every NPC in the world holds a single-step distortion of the same source text, so the rumour never drifts, the 2-hop target never sounds different from the 1-hop one, and the differentiating behaviour a studio would license this for does not exist. It is silently wrong today; the demo only looks right because the chain is hand-seeded (`demo_game/seeds/seed.py:957-980`).
- **Fix sketch:** Change `CYPHER_BATCH_EVENT_TRUST` to return `coalesce(k.distorted_summary, e.summary) AS summary` (the pattern `graph/reputation/reputation_queries.py:46` already uses) so the sharer relays *their own* account. Add a test that runs two hops and asserts hop-2 output contains hop-1's distortion marker.
- **Effort:** M
- **Blast radius:** `gossip_batch_queries.py`, the seed derived from `summary` (determinism fixtures in `test_gossip_determinism.py` will shift), `distortion_level` semantics (compounding needs a cap), and the eval golden set if any case pins a distorted string.

### [CR-L01-02] Stop the gossip batch write from overwriting an existing KNOWS_ABOUT edge back to clean `knows`

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `graph/gossip/gossip_batch_queries.py:53-62` — `MERGE (receiver)-[k:KNOWS_ABOUT]->(event) SET k.knowledge_state = w.knowledge_state, k.distortion_type = …, k.distorted_summary = …` unconditionally. Nothing in `CYPHER_BATCH_EVENT_TRUST` or `pair_selector.select_pairs` excludes a receiver who already knows the event. Live: `old_henryk` was seeded (`demo_game/seeds/seed.py:968-980`) with `knowledge_state: "rumor"`, `distortion_level: 70`, `"Word reached me the northmen have poured through king's pass, thousands dead. Utterly catastrophic…"`. At tick 600 the live graph reports `{"src_id":"old_henryk","source_character_id":"aldric_merchant","learned_at_tick":600,"knowledge_state":"knows","distortion_level":0,"distorted_summary":"The northern armies have crossed the border"}` — the seeded 2-hop distortion has been erased and replaced with clean canonical knowledge.
- **Cost of inaction:** Running the world *destroys* the demo. The scripted 5-minute scenario (`demo_game/runners/run.py:172,410` queries `old_henryk`) depends on him holding a distorted account; after ~600 ticks he holds the undistorted one. More broadly, knowledge monotonically regresses: any NPC's hard-won rumour is reset to `knows` the next time an undistorted propagation reaches them.
- **Fix sketch:** Guard the write — only overwrite when the incoming `distortion_level` exceeds the stored one, or when no edge exists (`ON CREATE SET` for the distortion fields, `ON MATCH SET` only `learned_at_tick`). Exclude receivers already holding `knowledge_state = 'knows'` in `CYPHER_BATCH_EVENT_TRUST`.
- **Effort:** M
- **Blast radius:** `gossip_batch_queries.py`, `rumor_trace_service.py` traces, the demo cache in `.cache/demo/`, and any eval case that advances the clock before asserting knowledge.

### [CR-L01-03] Wire `memory_consolidation_engine` into the tick scheduler — it has never run

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `api/dependencies_engines/__init__.py:138-162` builds the singleton `TickScheduler` and passes 25 engine slots; `memory_consolidation_engine` is not among them, and `_advanced_engine_kwargs()` (`:110-121`) returns 10 keys that do not include it — even though `get_memory_consolidation_engine()` exists at `api/dependencies_advanced/progression.py:96`. Therefore `tick_scheduler.py:530` `self._memory_consolidation_engine is None` is always true and `_maybe_consolidate_memory` returns immediately, leaving `response["consolidation"]` empty forever. Live confirmation — `GET /v1/admin/system/engines` at tick 598 returns exactly 27 engines (the 22 in `_ordered_tick_engines()` plus story_pacing, routine, chapter, gossip, event) and **`memory_consolidation` is absent from the list**.
- **Cost of inaction:** `docs/ENGINES.md` lists memory consolidation as step 6 of the tick order and the engine has its own contract YAML, prompt, LLM config and port. NPCs never consolidate dialogue into long-term memory autonomously; only the manual `POST /v1/admin/memories/consolidate/{npc_id}` route (`api/routes/knowledge/memories.py:275`) reaches it. This has presumably been true for the whole life of the engine and nothing surfaced it, because an unwired slot is silently `None`.
- **Fix sketch:** Add `memory_consolidation_engine=get_memory_consolidation_engine()` to `get_tick_scheduler()`, plus `consolidation_advance_interval` from settings. Add a test asserting every `BaseEngine | None` parameter of `TickScheduler.__init__` is supplied by the composition root.
- **Effort:** S
- **Blast radius:** Adds an LLM call to the tick path — check `skip_llm_engines` and tick latency budgets before enabling by default.

### [CR-L01-04] Narrow the dialogue degradation ladder's two bare `except Exception` blocks

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `engines/dialogue/degradation.py:103-128` — `except Exception` at `:107` (full tier) and `:119` (graph_only tier), both logging a warning and continuing, ending at `:128` with a canned `DialogueResponse` and HTTP **200**. Traced: `resolve_profile_for_turn` raises `RetrievalProfileNotFoundError` (`schema/retrieval_profile_models.py:193`) → `context_builder._validated_profile_for_turn:659` → `_build_dialogue_prompt` → `_run_llm_pipeline` (`dialogue_handler.py:413`) → `_full()` (`:226`) → caught at `degradation.py:107` → `_graph_only()` raises the same → caught at `:119` → canned. The route's handler at `api/routes/dialogue/dialogue.py:97` `except RetrievalProfileNotFoundError` is therefore **unreachable via `handler.handle()`**. The same two blocks convert a Neo4j outage into a canned 200 rather than the documented 503, and swallow `ContextBudgetError` from `context_budget_enforcer.py:74-88`.
- **Cost of inaction:** `utils/errors.py:306-317` states the class exists precisely so that "a run that silently fell back would record a `retrieval_profile` it never actually used, so an A/B arm would claim a variant that never ran — the class of silent divergence the eval programme exists to catch". On this branch (`eval-ab-context-arms`) that is exactly what happens: a typo'd arm name yields canned responses at 200 instead of a 4xx, and the arm looks merely bad rather than broken.
- **Fix sketch:** Re-raise a named allow-list before degrading — `RetrievalProfileNotFoundError`, `ContentRatingViolationError`, `ContextBudgetError`, `NodeNotFoundError` — and catch only `(LLMTimeoutError, LLMRequestError, asyncio.TimeoutError, neo4j.exceptions.Neo4jError)` per tier, mapping the Neo4j case to the documented 503.
- **Effort:** M
- **Blast radius:** Dialogue route status codes (some currently-200 turns become 4xx/503), the eval harness's expectations, and `test_dialogue_handler_fallback_v14.py`.

### [CR-L01-05] Replace the source-string test that "guards" the retrieval-profile 4xx

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `tests/unit/api/test_dialogue_retrieval_profile.py:71-82`:
  ```python
  def test_route_maps_an_unknown_profile_to_4xx() -> None:
      source = Path("src/npc_engine/api/routes/dialogue/dialogue.py").read_text(encoding="utf-8")
      assert "RetrievalProfileNotFoundError" in source
      assert "RETRIEVAL_PROFILE_NOT_FOUND" in source
  ```
  It passes today while the mapping it names is unreachable (CR-L01-04). Deleting the entire degradation-ladder re-raise would not change its result; neither would deleting the `except` clause it points at, as long as the identifier stays somewhere in the file.
- **Cost of inaction:** The one guard on the A/B programme's anti-silent-divergence invariant is green while the invariant is violated. Any future review that greps for "is this tested?" gets a false yes.
- **Fix sketch:** Replace it with a handler-level test: build a `DialogueHandler` with a stub context port that raises `RetrievalProfileNotFoundError`, call `handle()`, and assert the exception escapes rather than returning `degradation_level="canned"`.
- **Effort:** S
- **Removes:** ~12 lines
- **Blast radius:** none until CR-L01-04 lands; the replacement test is RED until then, which is the point.

### [CR-L01-06] Delete `TokenBudgetExceededError` or make the budget path actually fail

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `utils/errors.py:301` `class TokenBudgetExceededError(Exception):` — a bare `Exception`, violating the typed-hierarchy rule, and referenced nowhere in `src/` (`grep -rn "TokenBudgetExceededError" src/` returns only that definition). CLAUDE.md and `docs/PROMPT_DESIGN.md:91` both promise `context_builder.py` raises it. What the shipped path does instead: `context_budget_enforcer.py:213-217` and `:266-269` silently `continue` past items that do not fit; `:348 except ContextBudgetError: return []` drops a whole tier; `:366-373` breaks out of the trim loop and returns an **over-budget** prompt when only pinned/tier-0 items remain. The only raising function, `enforce_context_budget:74-88`, is called by nothing outside `__init__.py` re-exports and unit tests.
- **Cost of inaction:** Two documents and one exception class describe a fail-loud contract the engine does not honour; a reader budgeting prompt work trusts them. Meanwhile an over-budget prompt is handed to Ollama and truncated with no metric — the exact failure mode `96d83eb` spent a session diagnosing at the config level.
- **Fix sketch:** Delete the dead class and correct CLAUDE.md + `docs/PROMPT_DESIGN.md` to describe the real policy (drop-and-report), *and* make `_trim_to_serialized_budget`'s `break` at `:370` emit a WARNING with the overshoot so the undroppable case is observable.
- **Effort:** S
- **Removes:** ~4 lines + 2 doc claims
- **Blast radius:** `utils/errors.py`, CLAUDE.md, `docs/PROMPT_DESIGN.md`.

### [CR-L01-07] Re-measure the context-demand constants the new budget guard is frozen against

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `tests/unit/config/test_shipped_window_holds_the_measured_ceiling.py:45,53` hardcode `MEASURED_ROSTER_CEILING_TOKENS = 1151` and `MEASURED_TIER_MAXIMA = {"tier_a": 857, "tier_b": 96, "tier_c": 145}` from one run on 2026-08-27. Nothing re-derives them. Separately, `:104-106` `test_the_derived_budget_is_the_window_minus_the_named_overhead` asserts `_code_default_budget() == _code_default_window() - PROMPT_WINDOW_OVERHEAD_TOKENS`, and `_code_default_budget()` is *defined* at `:75` as `max(MIN_PROMPT_TOKEN_BUDGET, window - PROMPT_WINDOW_OVERHEAD_TOKENS)` — the assertion restates its own helper and can only fail if the 512 floor binds.
- **Cost of inaction:** The commit message for `96d83eb` correctly identifies that the *previous* guard was satisfied by construction. The replacement is stronger but is a snapshot: the next engine that adds a tier-A slot raises demand past 1151, the constants stay put, the test stays green, and tier-A items are dropped again — the same ~2.5-month silence, rediscovered the same way.
- **Fix sketch:** Make `make probe-ceiling` write its measurement to a checked-in JSON the test reads, and fail the gate when the recorded measurement is older than the last change to `retrieval/context/`. Delete the tautological assertion at `:104-106` or rewrite it to compare against the literal `12288 - 7130`.
- **Effort:** M
- **Blast radius:** the eval probe harness and `make check`.

### [CR-L01-08] Enforce or delete `EngineFallbackPolicy` — five engines declare a degradation policy nothing reads

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `engines/llm_config_models.py:68-75` defines `EngineFallbackPolicy(policy: Literal["graceful_degradation","fail_fast"], tiers: list[str])`, required on every `EngineModelConfig` (`:95`). Five YAMLs declare it: `engines/{chapter,dialogue,memory_consolidation,proactive_dialogue,quest_generation}/llm_config.yaml:14-17`, all `graceful_degradation`. `grep -rn "\.fallback\b\|fail_fast\|graceful_degradation" src/ --include=*.py` finds **no production read** — no branch anywhere consults `config.fallback.policy` or `.tiers`. The only readers are tests, and `tests/integration/test_engine_llm_config_integration.py:167` asserts `config.fallback.policy in ("graceful_degradation","fail_fast")` — true for every valid config by Pydantic construction. Similarly, `EngineTimeoutsMs.canned` and `.deterministic` (`:78-88`) are read nowhere; only `.full` and `.graph_only` reach code (`dialogue_handler.py:248-249`).
- **Cost of inaction:** Setting `policy: fail_fast` on any engine changes nothing. An integrator tuning degradation per engine gets silence. Four fields of validated configuration are ceremony.
- **Fix sketch:** Either make `execute_with_degradation` (and the equivalent path in the other four engines) read `config.fallback.policy`/`.tiers` — which is the natural home for the CR-L01-04 fix — or delete the field and its five YAML blocks.
- **Effort:** M (enforce) / S (delete)
- **Removes:** ~30 lines + 5 YAML blocks if deleted
- **Blast radius:** `llm_config_models.py` is `extra="forbid"`, so deletion requires editing all five YAMLs together.

### [CR-L01-09] Assert at the composition root that every tick engine slot is filled

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** All 26 engine parameters of `TickScheduler.__init__` (`scheduler/tick_scheduler.py:56-81`) are `BaseEngine | None = None`. `_run_tick_body:466-470` runs `if engine is not None:` — a `None` slot produces no log, no status-store entry, and an empty list in the response, which is byte-identical to an engine that ran and found nothing to do. CR-L01-03 is one instance found only by counting the live `GET /v1/admin/system/engines` payload (27 entries) against `_build_empty_response()`'s 29 keys (`:308-339`). No test compares the constructor's optional slots against `get_tick_scheduler()`'s kwargs.
- **Cost of inaction:** The next engine added to `_ordered_tick_engines()` but forgotten in `dependencies_engines/__init__.py` is invisible for months, exactly as memory consolidation was.
- **Fix sketch:** Add a unit test that introspects `inspect.signature(TickScheduler.__init__)` for `BaseEngine | None` parameters and asserts each appears in the kwargs `get_tick_scheduler()` passes; or make the scheduler log `tick_engine_not_wired` once per `None` slot at startup.
- **Effort:** S
- **Blast radius:** none — test-only, unless the log is added.

### [CR-L01-10] Make gossip side effects survive one bad pair

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `engines/gossip/gossip_handler.py:311-375` iterates `distortion_map` **after** `write_batch_knowledge_propagation` has already committed (`:182`). At `:333-335` a `create_rumor`/`believe_rumor` failure is logged and **re-raised**, aborting the whole loop; `tick_scheduler.py:239` then swallows it and discards the return value, so `propagated` and `seeds_used` are lost for the tick. Every pair after the failing one gets no rumour node, no `log_gossip` trust delta (`:354`), no emotion shock (`:341`) and no embedding refresh (`:360`) — while their `KNOWS_ABOUT` edges are already written.
- **Cost of inaction:** A single malformed event leaves the graph in a half-propagated state each tick: knowledge without rumours, and relationship trust that never moves. The `_run_engine_safe` catch-all means the operator sees one `tick_engine_error` line and a `last_error` string, with no indication that N pairs were skipped.
- **Fix sketch:** Move the `try` inside the per-pair loop, count failures, and return them in the tick result dict instead of re-raising; or run the batch write and the side effects in one transaction via `transaction_coordinator.run_in_tx`.
- **Effort:** M
- **Blast radius:** `gossip_handler.run_tick` return shape (`test_gossip_determinism.py` asserts `seeds_used`), and `tick_scheduler`'s `response["gossip"]`.

### [CR-L01-11] Log the event-sampling RNG seed, as gossip already does

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `engines/events/event_handler.py:129` `rng = self._rng or random.Random(tick_id)` — no log line anywhere in `_select_template` or `run_tick`; `grep -n "seed" engines/events/event_handler.py` returns only the docstring word "seeding". Gossip logs both the seed and the probability at `gossip_handler.py:243-251` and returns `seeds_used` in the tick result. `event_handler.py:171` also returns `{"tick_id": …, "created": 0}` when `scoped_locations` is empty, with no log, so "no eligible location" and "template misconfigured" look identical from outside.
- **Cost of inaction:** An event stream that stops generating is undiagnosable without attaching a debugger; live, `event` last ran at tick 580 while the clock is at 598 and there is no record of what it sampled.
- **Fix sketch:** Log `event_rng seed=%d tick=%d template=%s` at DEBUG in `_select_template`, and add a DEBUG line to the empty-`scoped_locations` exit naming the template.
- **Effort:** S
- **Blast radius:** none.

### [CR-L01-12] Delete `engines/currency/` and `engines/deception/` — nothing calls them

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** Mechanical import scan across all of `src/npc_engine`: `currency` and `deception` are the only two of 39 `engines/` subpackages with **zero** external importers. `engines/currency/` is 12 lines — an `__init__.py` whose docstring still reads `Public surface: (list re-exports here)` and contains nothing but `from __future__ import annotations`. `engines/deception/` is 128 lines; `grep -rn "engines.deception" src/ tests/ demo_game/ scripts/ evals/` finds only its own `__init__.py:12` and `tests/unit/engines/test_deception_engine.py:35`. Nothing in `api/`, `scheduler/` or the demo constructs a `DeceptionEngine`.
- **Cost of inaction:** `docs/ENGINES.md` presents ~40 engines as the product's surface; two of them are not connected to anything, which inflates the "40 engines" figure that a scope conversation would start from. Small, but it is the cheapest subtraction available.
- **Fix sketch:** Delete both packages and `test_deception_engine.py`; if deception is roadmap work, move it to a branch and remove the placeholder from the catalog.
- **Effort:** S
- **Removes:** ~140 lines / 5 files
- **Blast radius:** `docs/ENGINES.md` count; deletion requires human approval per CLAUDE.md's "deleting a file you did not create" rule.

### [CR-L01-13] Give the six engine contracts either full coverage or an honest scope note

- **Severity:** LOW
- **Confidence:** Likely
- **Kind:** Gap
- **Evidence:** `engines/contracts/` holds 6 YAMLs (`chapter`, `currency`, `dialogue`, `memory_consolidation`, `quest`, `quest_generation`) for 39 engine subpackages. `src/npc_engine/scripts/check_contracts.py:36-52` validates the contracts that exist and checks their declared test files resolve; it has no notion of "every engine must have a contract", so the 33 without one are not a gate failure. One of the six (`currency_engine.yaml`) describes a package that is an empty namespace (CR-L01-12). `docs/ENGINES.md:60` tells the reader "Engines that call an LLM declare `uses_llm: true` in their engine contract", which is true of 4 files and false as a general statement.
- **Cost of inaction:** A reader treats the contract system as the engine registry it looks like. It covers 15% of engines and one of its entries is empty.
- **Fix sketch:** Either add a gate requiring one contract per `engines/*/` package with a public `run_tick`/handler, or amend `docs/ENGINES.md` and the `contracts/__init__.py` docstring to say the system covers a named subset and why.
- **Effort:** S (doc) / L (full coverage)
- **Blast radius:** `make check` if the gate is added.

---

## Method notes

- Live reads used: `GET /v1/admin/system/engines`, `GET /v1/clock/state`,
  `GET /v1/graph/edges/KNOWS_ABOUT?dst_id=…`. No writes, no clock advance, no seeding.
- The 66-site silent-`except` census was produced by an AST-free indentation scan over
  `engines/ services/ retrieval/ scheduler/ graph/` flagging every `except` whose block contains
  no `raise`; the script lives in the session scratchpad and is not checked in.
- Neo4j is not published to the host, so all graph facts came through the API.
